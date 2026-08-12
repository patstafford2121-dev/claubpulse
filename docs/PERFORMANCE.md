# Performance & method

Everything below was produced with MT5's Strategy Tester on FxPro price data,
"1-minute OHLC" model unless noted (spot-checked against the every-tick model
where it mattered). Deposit $10,000, leverage 1:100. **Backtests are backward
looking; none of this is a promise.**

## 1. Replication parity (why we trust the engine)

ClaubPulse was validated against a commercial reference streak EA by running
identical inputs on identical data and comparing aggregate behavior:

| Metric (S&P 500 H1, 2024-08 → 2026-08) | Reference EA | ClaubPulse |
|---|---|---|
| Net profit | +$9,262 | +$8,105 |
| Profit factor | 1.88 | 1.78 |
| Trades (long/short) | 70 (69/1) | 67 (67/0) |
| Equity drawdown | 43.3% | 46.3% |

Re-confirmed on H4 presets (PF 0.79 vs 0.77 and 0.77 vs 0.75, trade counts
within 2%). The residual gap is unobservable execution micro-detail.

Behavioral findings locked in during replication (variants tested and
**rejected** in brackets):

- Entries are **contrarian**: bearish streak → BUY, bullish streak → SELL
  [momentum mapping: inverted results]
- Candle direction is close-vs-open [close-vs-prior-close: worse]
- **Dojis are skipped**, streaks continue through them [doji-reset: fewer,
  worse trades]
- Signals evaluate on completed bars, enter next bar [intrabar forming-bar
  signals: more trades, much worse]
- Sizing on equity [balance: marginally worse]
- Trailing is classic distance+step [tight step-as-distance: cuts winners]

## 2. What works (thinly) and what doesn't

**Works, with eyes open:**

- **S&P 500 H1** (the reference config): PF ~1.8, but structurally long-biased
  (dip-buying an uptrending index) — a 2-year walk-forward showed 6/8 positive
  quarters and **−24% in the one sustained correction quarter**. Returns track
  index direction.
- **GBPUSD M5 "Cable"**: PF 1.11–1.12 at ~7.7 trades/day, 8% DD, trades both
  directions ~50/50. Stable across tick models — but the 24-month view shows
  year one ≈ breakeven; the edge is thin and recent.

**Doesn't work — published so you don't have to rediscover it:**

- Every vendor-published H4 preset we tested (S&P 500, moderate and
  aggressive tiers) is net-losing over 2024–2026 (PF 0.75–0.87). Raising risk
  just loses faster (−70% to −92% of the account at 3.4% risk).
- **High-frequency configs are spread-donation machines.** All M5 4/4-streak
  configs trade ~30×/day at PF 0.58–0.94. A ~340-combination optimization
  sweep found **zero** profitable high-frequency EURUSD passes.
- **The overfitting object lesson:** gold M30/M15 optimization found an
  in-sample ridge at PF 1.4–1.48 (~10–21 trades/day, +$29k in-sample). Every
  top config **failed the held-out walk-forward** (PF 0.88–1.00, drawdowns to
  73%). The "edge" was a photograph of the 2024–25 gold bull market. If you
  optimize this EA yourself, hold out data and expect this outcome.

## 3. Reproducing

Headless tester configs look like:

```ini
[Tester]
Expert=ClaubPulse
Symbol=#USSPX500
Period=H1
Model=1
FromDate=2024.08.01
ToDate=2026.08.08
Deposit=10000
Currency=USD
Leverage=100
Report=reports\my_run
ShutdownTerminal=1

[TesterInputs]
magicNumber=79001
iLots=0
percRisk=3.4
iMaxOrders=3
stopLoss=23000
takeProfit=35000
iTrailingStart=33000
iTrailingStep=7500
iBullishX=12
iBearishX=4
```

Run: `terminal64.exe /portable /config:path\to\config.ini`. Note some MT5
builds ignore `ExpertParameters=` .set files headlessly — pass inputs via
`[TesterInputs]` as above.
