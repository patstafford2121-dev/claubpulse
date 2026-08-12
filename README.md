# ClaubPulse

An open, owned, clean-room **streak-contrarian trading EA for MetaTrader 5**,
plus a local web dashboard ("ClaubPulse Command") with live stats, an
equity chart, a signal speedo, a force-graph trade constellation, and a
gamified progress layer.

> ⚠️ **Read this first.** This is trading *software*, not financial advice.
> Leveraged CFD/futures trading can lose more than you deposit. Backtests are
> not promises; several configurations documented here **lose money on
> purpose** to show you the method. The only sane path is
> **backtest → demo account → only then money you can afford to lose entirely.**

## The strategy, in one paragraph

ClaubPulse counts consecutive candles. After `iBearishX` consecutive bearish
candles it **buys the dip**; after `iBullishX` consecutive bullish candles it
**sells the fade** (contrarian — verified against a commercial reference bot
by parity backtesting; see [PROVENANCE.md](PROVENANCE.md)). Dojis are skipped,
not streak-resetting. Sizing is percent-of-equity against the stop distance
(or fixed lots), exits are fixed SL/TP in points with a classic distance+step
trailing stop, and a magic number keeps it from touching anything it didn't
open. ~200 lines of MQL5 you can read in ten minutes: [`ea/ClaubPulse.mq5`](ea/ClaubPulse.mq5).

## Honest performance

Full methodology and tables in [docs/PERFORMANCE.md](docs/PERFORMANCE.md).
The short version, all on FxPro data via MT5's Strategy Tester:

| Config | Window | Result |
|---|---|---|
| S&P 500 H1 (percRisk 3.4) | 2024-08 → 2026-08 | **+81%, PF 1.78**, 46% equity DD |
| S&P 500 H1 (percRisk 1.7) | same | +45%, PF 1.86, 24% DD (reference EA) |
| GBPUSD M5 "Cable" preset | 12 mo | +15%, PF 1.11–1.12, ~7.7 trades/day, 8% DD |
| Every published H4 preset we tested | 2 yr | **loses money** (PF 0.75–0.87) |
| Optimized gold day-trading configs | walk-forward | **in-sample PF 1.48 → out-of-sample 0.88; rejected** |

We publish the failures because they are the point: this engine has a thin,
regime-dependent edge in a few configurations and **no edge at all at high
frequency** — anyone telling you otherwise about a streak bot is selling
something.

## Quick start

1. **See the dashboard with zero setup** (synthetic sample data):
   ```
   cd dashboard
   python claub_dash.py        # then open http://127.0.0.1:8787
   ```
2. **Compile the EA**: open `ea/ClaubPulse.mq5` in MetaEditor → Compile
   (or CLI: `metaeditor64.exe /portable /compile:"...\ClaubPulse.mq5"`).
3. **Demo first**: open a demo account in MT5, drag ClaubPulse onto a chart,
   load a preset from `ea/presets/`, and let it paper trade. Details in
   [docs/SETUP.md](docs/SETUP.md) — including the ×10 point-scaling gotcha on
   some brokers' index feeds.
4. **Live** is your decision and your risk. Nothing here needs a license key,
   an account with anyone, or a subscription. That's the point.

## The dashboard

`dashboard/claub_dash.py` reads your MT5 terminal **read-only** through the
official MetaTrader5 Python package and serves a single-page dashboard:
hero P&L + equity/balance chart, per-strategy signal panels with live candle
strips, a contrarian signal speedo, open positions and closed-trade history,
a force-directed "trade constellation" graph, and an XP/achievements layer
computed from your actual closed trades. Configure via `claub_config.json`
(copy the example); `demo_mode: true` serves synthetic data.

## License

MIT — see [LICENSE](LICENSE). No warranty of any kind.
