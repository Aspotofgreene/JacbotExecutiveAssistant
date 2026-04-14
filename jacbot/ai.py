"""
AI helpers for Jacbot — backed by local Ollama endpoints.

Routing:
  - Light tasks (evaluate_tasks, categorize_tasks) → Mac mini / qwen3
  - Heavy tasks (weekly/monthly/yearly reports)    → Desktop GPU / deepseek-r1

Ollama exposes an OpenAI-compatible API at /v1, so we use the `openai` SDK
pointed at two different base_urls. No API key is required but the SDK
demands a non-empty string.

Local reasoning models (deepseek-r1, qwen3) emit <think>…</think> blocks —
we strip those before returning. JSON parsing is forgiving of code fences.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date

from openai import OpenAI

from jacbot import config

logger = logging.getLogger(__name__)

_light_client: OpenAI | None = None
_heavy_client: OpenAI | None = None


def _base_url(root: str) -> str:
    root = root.rstrip("/")
    return root if root.endswith("/v1") else root + "/v1"


def _get_light_client() -> OpenAI:
    global _light_client
    if _light_client is None:
        _light_client = OpenAI(base_url=_base_url(config.OLLAMA_MAC_URL),
                               api_key="ollama")
    return _light_client


def _get_heavy_client() -> OpenAI:
    global _heavy_client
    if _heavy_client is None:
        _heavy_client = OpenAI(base_url=_base_url(config.OLLAMA_DESKTOP_URL),
                               api_key="ollama")
    return _heavy_client


# ─────────────────────────────────────────────────────────────────────────────
# Output cleaning
# ─────────────────────────────────────────────────────────────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> reasoning blocks."""
    return _THINK_RE.sub("", text).strip()


def _extract_json(text: str):
    """Forgiving JSON extraction: handles fenced blocks and leading/trailing text."""
    text = _strip_thinking(text)

    # 1. direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. fenced ```json … ```
    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 3. first [ … last ] or first { … last }
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                continue

    raise ValueError(f"could not parse JSON from model output: {text[:200]!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Task evaluation (Mac mini — qwen3)
# ─────────────────────────────────────────────────────────────────────────────

EVAL_SYSTEM = """\
You are a personal productivity coach helping someone set clear, actionable daily priorities.

When given a list of 3 tasks, evaluate each one and return a JSON array with exactly 3 objects.
Each object must have:
  - "original": the original task text
  - "issues": list of strings describing any problems (empty list if none)
  - "suggestion": an improved version of the task (same as original if no improvement needed)
  - "effort_min": estimated minutes to complete (integer)
  - "feedback": one short encouraging sentence (max 15 words)

Issue types to check:
  - "vague": no clear deliverable (e.g. "work on project")
  - "too_big": likely >3 hours (e.g. "build the entire app")
  - "no_action_verb": doesn't start with an action word
  - "missing_context": needs who/what/where to be actionable

Be concise and encouraging. Return ONLY valid JSON, no markdown, no commentary."""


def evaluate_tasks(tasks: list[str], whys: list[str | None]) -> list[dict]:
    """Evaluate 3 tasks for clarity and scope (Mac mini / qwen3)."""
    task_lines = []
    for i, (task, why) in enumerate(zip(tasks, whys), 1):
        line = f"{i}. {task}"
        if why:
            line += f" (reason: {why})"
        task_lines.append(line)

    prompt = "Evaluate these 3 tasks:\n\n" + "\n".join(task_lines)

    try:
        client = _get_light_client()
        response = client.chat.completions.create(
            model=config.OLLAMA_MAC_MODEL,
            messages=[
                {"role": "system", "content": EVAL_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        raw = response.choices[0].message.content or ""
        result = _extract_json(raw)
        if isinstance(result, list) and len(result) == 3:
            return result
        logger.warning("Task eval returned wrong shape: %r", result)
    except Exception as e:
        logger.error("Task evaluation failed: %s", e)

    # Fallback: return tasks as-is with no issues
    return [{"original": t, "issues": [], "suggestion": t,
             "effort_min": 60, "feedback": "Go get it."} for t in tasks]


# ─────────────────────────────────────────────────────────────────────────────
# Categorization (Mac mini — qwen3)
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = [
    "Deep Work", "Admin", "Health", "Relationships",
    "Side Project", "Learning", "Finance", "Other"
]

CATEGORY_SYSTEM = f"""\
Categorize tasks into one of these categories: {', '.join(CATEGORIES)}.
Return a JSON array of category strings, one per task, in the same order.
Return ONLY valid JSON, no markdown, no commentary."""


def categorize_tasks(task_texts: list[str]) -> list[str]:
    """Return a category string for each task (Mac mini / qwen3)."""
    if not task_texts:
        return []
    prompt = "Categorize these tasks:\n" + "\n".join(f"- {t}" for t in task_texts)
    try:
        client = _get_light_client()
        response = client.chat.completions.create(
            model=config.OLLAMA_MAC_MODEL,
            messages=[
                {"role": "system", "content": CATEGORY_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
        result = _extract_json(raw)
        if isinstance(result, list):
            return [str(c) for c in result[:len(task_texts)]]
    except Exception as e:
        logger.error("Categorization failed: %s", e)
    return ["Other"] * len(task_texts)


# ─────────────────────────────────────────────────────────────────────────────
# Reports (Desktop GPU — deepseek-r1)
# ─────────────────────────────────────────────────────────────────────────────

def _build_task_summary(tasks: list) -> str:
    lines = []
    for t in tasks:
        status = t["status"]
        category = t["ai_category"] or "Uncategorized"
        carried = " (carried)" if t["carried_from_id"] else ""
        lines.append(f"- [{status.upper()}] [{category}] {t['text']}{carried}")
    return "\n".join(lines) if lines else "No tasks recorded."


def _build_journal_summary(entries: list) -> str:
    if not entries:
        return "No journal entries."
    return "\n".join(f"- {e['text'][:200]}" for e in entries)


def _heavy_chat(prompt: str, max_tokens: int) -> str:
    client = _get_heavy_client()
    response = client.chat.completions.create(
        model=config.OLLAMA_DESKTOP_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.6,
    )
    return _strip_thinking(response.choices[0].message.content or "")


def generate_weekly_report(
    tasks: list,
    journal_entries: list,
    week_start: date,
    week_end: date,
    theme: str | None = None,
) -> str:
    task_summary = _build_task_summary(tasks)
    journal_summary = _build_journal_summary(journal_entries)
    fresh_tasks = [t for t in tasks if not t["carried_from_id"]]
    done = sum(1 for t in fresh_tasks if t["status"] == "done")
    total = len(fresh_tasks)
    rate = f"{round(done/total*100)}%" if total else "n/a"

    theme_note = f"\nThis week's stated theme: {theme}" if theme else ""

    prompt = f"""Weekly accountability report for {week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}.

Completion rate: {done}/{total} tasks ({rate}){theme_note}

TASKS:
{task_summary}

JOURNAL NOTES:
{journal_summary}

Write a weekly summary with these sections:
1. **This Week** — 2-3 sentence honest summary of what got done and what didn't
2. **Patterns** — what themes or categories dominated? Any tasks that kept carrying?
3. **Wins** — celebrate what was completed
4. **Watch out for** — one honest observation about a pattern or risk
5. **Next week** — one suggested focus area

Be direct, honest, and encouraging. No fluff. Max 300 words."""

    try:
        return _heavy_chat(prompt, max_tokens=1024)
    except Exception as e:
        logger.error("Weekly report failed: %s", e)
        return f"Weekly report generation failed: {e}"


def generate_monthly_report(tasks: list, journal_entries: list,
                             month_start: date, month_end: date) -> str:
    task_summary = _build_task_summary(tasks)
    fresh_tasks = [t for t in tasks if not t["carried_from_id"]]
    done = sum(1 for t in fresh_tasks if t["status"] == "done")
    total = len(fresh_tasks)
    killed = sum(1 for t in fresh_tasks if t["status"] == "killed")

    prompt = f"""Monthly productivity report for {month_start.strftime('%B %Y')}.

Stats: {done}/{total} tasks completed, {killed} killed/abandoned.

TASKS:
{task_summary}

JOURNAL HIGHLIGHTS:
{_build_journal_summary(journal_entries)}

Write a monthly report with:
1. **Month in Review** — honest 2-3 sentence summary
2. **Where your time went** — category breakdown with observations
3. **Carried tasks analysis** — any tasks that dragged on too long?
4. **Best days/periods** — when were you most productive?
5. **Next month focus** — one clear recommendation

Be analytical and honest. Max 400 words."""

    try:
        return _heavy_chat(prompt, max_tokens=1500)
    except Exception as e:
        logger.error("Monthly report failed: %s", e)
        return f"Monthly report generation failed: {e}"


def generate_yearly_report(tasks: list, journal_entries: list, year: int) -> str:
    fresh_tasks = [t for t in tasks if not t["carried_from_id"]]
    done = sum(1 for t in fresh_tasks if t["status"] == "done")
    total = len(fresh_tasks)

    from collections import Counter
    categories = Counter(t["ai_category"] or "Uncategorized" for t in fresh_tasks)
    cat_summary = "\n".join(f"  {cat}: {count}" for cat, count in categories.most_common())

    prompt = f"""Yearly reflection report for {year}.

Overall: {done}/{total} tasks completed ({round(done/total*100) if total else 0}% completion rate)

Category breakdown:
{cat_summary}

Journal entries this year: {len(journal_entries)}

Sample journal themes (first 20 entries):
{_build_journal_summary(journal_entries[:20])}

Write an inspiring but honest yearly narrative with:
1. **The Story of Your Year** — 3-4 sentences capturing the overall arc
2. **What You Focused On** — top categories and what they reveal
3. **Growth Moments** — patterns of improvement
4. **Unfinished Business** — recurring themes that never got resolved
5. **A Note for Next Year** — one piece of advice to your future self

Be thoughtful, narrative, and personal. Max 500 words."""

    try:
        return _heavy_chat(prompt, max_tokens=2000)
    except Exception as e:
        logger.error("Yearly report failed: %s", e)
        return f"Yearly report generation failed: {e}"
