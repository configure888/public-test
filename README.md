# Institutional Pattern Intelligence — Pine v3.2

A TradingView Pine v6 research indicator for systematic market-structure, liquidity, pattern and execution-state classification.

Current build is compiled on every push through the open-source `tradesdontlie/tradingview-mcp` `pine_check()` path against TradingView's server-side Pine compiler.

## What the indicator does

The indicator separates two primary setup families:

- **Reversal:** liquidity sweep → MSS/CHOCH → displacement → FVG → PD-array retracement → external-liquidity DOL.
- **Continuation:** HTF/MTF trend → BOS → compression/pullback → displacement/FVG → PD-array re-entry → external liquidity.

Context includes:

- confirmed swing graph, BOS/CHOCH and liquidity sweeps;
- FVG / IFVG;
- order blocks and mitigation;
- OTE 0.62–0.79 with 0.705 sweet spot;
- EQH/EQL and weak/strong liquidity references;
- PDH/PDL/PWH/PWL DOL targets;
- dual-reference SMT;
- regular and hidden RSI divergence;
- classical geometry as secondary evidence;
- 5m / 15m / 1h matrix + intermediate/HTF narrative;
- compression/coil, ADX/volatility regime, VWAP deviation and session context;
- optional BTC/Coinlegs or inverse macro context;
- projected reward/risk to a pre-declared DOL;
- grouped research scores designed to reduce correlated-confluence double counting.

## Jev

Jev is an optional downstream adjudicator, never the execution engine.

Pine generates deterministic candidates. External code may enrich them with L2/order-flow data, ask Jev narrow typed questions, then apply hard deterministic vetoes. Sizing, wallet access, stops and order execution remain outside the model.

## Research mode

Turn on **Export Research Candidates** and create a TradingView alert using `Any alert() function call`. The indicator emits a JSON feature vector suitable for outcome labeling and meta-model calibration.

See:

- `docs/DEEP_RESEARCH.md`
- `docs/VALIDATION_PROTOCOL.md`
- `research/README.md`
- `research/label_candidates.py`
- `research/validate.py`
- `research/jev_policy.py`

## Performance target

80% win rate at 6R+ is a research target, not a repository claim. The validation protocol explicitly prevents small-sample, survivorship and repeated-backtest optimization from being presented as evidence of that performance.
