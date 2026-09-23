# Research tooling

The Pine indicator emits `research_candidate` JSON via TradingView `alert()` when `Export Research Candidates` is enabled.

## 1. Capture candidates

Store webhook payloads as newline-delimited JSON (`candidates.jsonl`). Do not keep only A+ trades; the export is intentionally earlier than the final gate so calibration has negative examples.

## 2. Label candidates

Prepare OHLCV CSV with columns:

```text
timestamp,open,high,low,close,volume
```

Then:

```bash
python research/label_candidates.py \
  --candidates data/candidates.jsonl \
  --ohlcv data/BTCUSDT_5m.csv \
  --out data/labeled.jsonl \
  --horizon 100
```

The labeler reports MFE/MAE, first-touch bars for 1R/2R/3R/4R/6R/8R/10R, stop timing, DOL timing, terminal R and a conservative `contract_r`. If stop and +6R occur in the same OHLC bar, stop wins.

## 3. Validate

```bash
python research/validate.py \
  --labeled data/labeled.jsonl \
  --out reports/validation.json \
  --folds 5 \
  --bootstrap 5000 \
  --block 10
```

Reports:

- 6R-before-stop win rate + Wilson interval;
- expectancy / median R;
- mean MFE / MAE;
- max drawdown in R;
- chronological folds;
- family, symbol, timeframe and grouped-score buckets;
- block-bootstrap intervals.

## 4. Jev policy

`jev_policy.py` is deliberately boring. It does not call a model or place an order. It receives a typed Jev judgment and a Pine candidate and returns `ACCEPT` or `ABSTAIN` under deterministic thresholds.

Thresholds must be calibrated from OOS data rather than chosen because they make one backtest look good.
