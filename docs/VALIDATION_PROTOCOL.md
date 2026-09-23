# Validation Protocol

This document is the acceptance contract for any claim that the strategy has high win rate, high R, or production readiness.

## 1. Dataset contract

Each candidate must be generated without future information and include:

- unique event id;
- event/bar time;
- symbol and timeframe;
- side and setup family;
- entry, structural stop and pre-declared target/DOL;
- grouped evidence score and its component buckets;
- raw feature flags;
- projected R before outcome;
- whether the candidate passed the live A+ gate.

Research export defaults to **not requiring 6R** so the dataset includes candidates that fail the final gate. This is intentional.

## 2. Outcome contract

Default labeling uses first-touch barriers relative to initial risk:

- stop = -1R;
- checkpoints = +1R, +2R, +3R, +4R, +6R, +8R, +10R;
- DOL hit tracked separately;
- MFE and MAE measured in R;
- horizon fixed before the test;
- if stop and target are both inside the same OHLC bar and intrabar order is unknown, **count stop first**.

The conservative same-bar rule prevents artificial wins caused by OHLC sequencing ambiguity.

## 3. Cost contract

The first research labels measure market-path feasibility. Production evaluation must additionally include:

- maker/taker fee actually applicable to the venue/account tier;
- spread at decision time;
- entry slippage;
- stop slippage / gap behavior;
- funding/borrow where applicable;
- missed fills for limit-entry simulations;
- latency assumptions for webhook → decision → order routing.

Do not convert a path-label backtest into a PnL claim without an execution model.

## 4. Split contract

Use chronological splits. Never shuffle events randomly.

Recommended sequence:

1. discovery window;
2. calibration/validation window;
3. frozen untouched test window;
4. forward paper/shadow period;
5. only then limited live deployment.

Where event outcome windows overlap a fold boundary, purge those events. Apply an embargo after the training boundary if future labels could bleed into the next fold.

## 5. Required reports

At minimum report:

- number of independent-ish candidates;
- 6R-before-stop win rate;
- 95% Wilson interval;
- expectancy in R;
- median R;
- mean MFE and MAE;
- maximum sequential drawdown in R;
- results by chronological fold;
- results by symbol/timeframe;
- reversal vs continuation;
- grouped-score buckets;
- A+ vs pre-A+ candidates;
- with/without each feature family;
- cost-adjusted results;
- parameter/configuration trial count.

## 6. Anti-overfit rules

- Every tried configuration counts as a trial, even if discarded.
- Do not repeatedly inspect the final test and then change the model.
- Do not choose a feature because it works on the same period used to report performance.
- Report degradation from train → validation → test.
- Prefer broad plateaus over isolated parameter optima.
- Use block bootstrap for clustered events.
- When many variants are compared, add PBO/Deflated-Sharpe analysis before capital allocation.

## 7. Claim thresholds

No strategy should be described as “80% WR / 6R” because one backtest prints those numbers.

A defensible claim needs:

- frozen OOS results;
- enough observations for a narrow confidence interval;
- stability across folds/regimes;
- realistic execution costs;
- no single asset/year dominating the result;
- no catastrophic tail hidden by average statistics;
- forward paper/shadow confirmation.

For orientation only: if 300 independent trades have an observed 80% win rate, the Wilson 95% lower bound is about 75%. Correlation and overlapping signals reduce effective sample size.

## 8. Jev comparison

Jev must be evaluated as an incremental meta-filter:

- same frozen Pine candidates;
- same execution assumptions;
- Pine-only arm;
- Pine + deterministic meta-filter baseline;
- Pine + Jev arm;
- compare acceptance rate, 6R hit rate, expectancy, drawdown, Brier/log loss/ECE and calibration reliability.

If Jev only improves in-sample classification but not economic outcomes, it is removed.
