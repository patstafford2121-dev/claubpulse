# Provenance

ClaubPulse is a **clean-room implementation** of a well-known public trading
idea: consecutive-candle ("streak") contrarian entries with fixed stops,
percent-risk sizing, and a step trailing stop.

- The EA was written from scratch in MQL5 by the authors. **No third-party
  code was copied, decompiled, disassembled, or otherwise inspected.**
- Behavior was specified from two public sources: vendor-published settings
  values for a commercial streak EA, and black-box observation (backtest
  parity comparisons of trade counts, direction mix, and aggregate outcomes
  on identical data).
- Input parameter *names* intentionally match the conventional names used by
  commercial streak EAs so that published preset files port unchanged. Names
  and numeric settings are functional facts, not creative expression.
- This project is **not affiliated with, endorsed by, or derived from any
  commercial EA vendor**, and no vendor's product code, branding, or
  marketing material is included or used here.

The full replication method (including the behavioral variants tested and
rejected) is documented in [docs/PERFORMANCE.md](docs/PERFORMANCE.md).
