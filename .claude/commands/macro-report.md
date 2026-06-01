---
description: Generate this week's Weekly Macro Investor Report (US + Canada + Global)
argument-hint: "[week-ending date, e.g. 2026-05-31 — optional, defaults to most recent Saturday]"
allowed-tools: Task, WebSearch, WebFetch, Read, Write
---

Generate the Weekly Macro Investor Report.

Week-ending date: **$ARGUMENTS** (if blank, use the most recent Saturday relative to
today's date).

Use the `macro-investor-report` subagent to do the work. It should:
1. Scan the past week's news with live web search across all eight indicators —
   inflation, unemployment, central bank policy, earnings growth, bond yields, oil
   prices, valuations, and recession probability — for the **U.S.** and **Canada**,
   plus a tighter **Global** section (ECB/BoE, BoJ/China, geopolitics & commodities).
2. Confirm every quantitative figure against a dated source found this session; flag
   anything it cannot confirm rather than guessing.
3. Write the report to `reports/macro-report-<week-ending-date>.md` in the house
   format defined in the subagent, including the Scorecard, Market Regime, Watchlist
   Notes, an overall bullish/cautious percentage, and a Sources list.

When the subagent finishes, give me a 4-6 line chat summary that leads with the
overall bull/bear read and the top risks, and link to the generated file.
