# Setup

## Compile

Open `ea/ClaubPulse.mq5` in MetaEditor (F4 from MT5) and hit **Compile** —
zero errors, zero warnings expected. Headless:

```
metaeditor64.exe /portable /compile:"C:\path\to\ClaubPulse.mq5" /log:"C:\path\to\ClaubPulse.log"
```

(`/portable` matters for portable installs — without it MetaEditor resolves
includes against the roaming profile and fails.)

## Attach (demo account first — always)

1. In MT5: File → **Open an Account** → pick your broker → **demo**.
2. Open a chart of your symbol/timeframe (e.g. #USSPX500 H1, GBPUSD M5).
3. Drag **ClaubPulse** from the Navigator onto the chart → **Load** a preset
   from `ea/presets/` → set a unique `magicNumber` per chart → OK.
4. Enable **Algo Trading** (toolbar button). The journal should show
   `expert ClaubPulse (SYMBOL,TF) loaded successfully`.

Running multiple strategies = multiple charts, each with its own magic number.

## The ×10 points gotcha

"Points" are broker-feed-dependent. Published streak-EA settings often assume
a coarser feed than your broker quotes. Example: on FxPro's #USSPX500
(2-decimal quotes, point = 0.01) vendor settings of SL 2300 are 10× too tight
— the correct value is 23000. **Sanity-check every preset**: SL points ×
point size should be a sensible price distance for the instrument. Get this
wrong and you'll either get "[Invalid stops]" rejections (lucky) or a
position sized 10× too aggressively that stops out on noise (unlucky).

## Dashboard

```
cd dashboard
copy claub_config.example.json claub_config.json   # then edit
pip install MetaTrader5                            # Windows only
pythonw claub_dash.py                              # http://127.0.0.1:8787
```

- `terminal_exe` must point at the exact terminal the EA runs in; the poller
  attaches **read-only** and never launches a terminal itself.
- `demo_mode: true` serves synthetic data — useful to preview the UI.
- The `strategies` list drives the per-strategy panels; `magic` must match
  each chart's `magicNumber`.
- The dashboard binds to 127.0.0.1 only. If you expose it beyond localhost,
  that's on you — add auth in front of it.

## Inputs reference

| Input | Meaning |
|---|---|
| `magicNumber` | order tag; the EA only manages its own trades |
| `iLots` | fixed lot size; 0 = size from `percRisk` |
| `percRisk` | % of equity risked to the stop per trade |
| `iMaxOrders` | max concurrent positions (≤0 = unlimited) |
| `stopLoss` / `takeProfit` | points |
| `iTrailingStart` | profit in points before the trail arms; also the trail distance |
| `iTrailingStep` | minimum improvement in points before SL moves again |
| `iBullishX` | consecutive bullish candles that trigger a SELL (fade) |
| `iBearishX` | consecutive bearish candles that trigger a BUY (dip) |
