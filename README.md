# JacbotExecutiveAssistant

My own personal EA.

## Weekly Macro Investor Report agent

An agent that scans the past week's news for events that move markets and produces a
disciplined **Weekly Macro Investor Report** covering the U.S. and Canada in detail,
plus a tighter Global section.

Rather than asking "which stock will go up," it monitors the economic conditions that
influence all assets, across eight indicators:

1. Inflation
2. Unemployment
3. Central bank policy
4. Earnings growth
5. Bond yields
6. Oil prices
7. Valuation metrics
8. Recession probability

For each indicator it reports **status → interpretation → market impact → watch
level** (🟢 / 🟡 / 🟠 / 🔴), then rolls everything into a scorecard, a market-regime
read, watchlist notes, and an overall bullish/cautious percentage.

### How to use it

Inside Claude Code, run the slash command:

```
/macro-report                 # most recent week (defaults to last Saturday)
/macro-report 2026-05-31      # a specific week-ending date
```

The `/macro-report` command launches the `macro-investor-report` subagent, which uses
live web search to gather the week's data, confirms every figure against a dated
source (flagging anything it can't confirm rather than guessing), and writes the
report to `reports/macro-report-<week-ending-date>.md`.

### Layout

```
.claude/
  agents/macro-investor-report.md   # the analyst subagent (the "brain")
  commands/macro-report.md          # the /macro-report slash command (launcher)
reports/
  SAMPLE-macro-report-2026-05-31.md # illustrative format reference
  macro-report-<date>.md            # generated reports land here
```

### Notes

- **Educational only — not financial advice.** The report informs; it does not tell
  anyone to buy or sell.
- Quantitative claims come from sources found at generation time and are cited with
  dates. Unconfirmed items are explicitly flagged.
