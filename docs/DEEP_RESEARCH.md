# Deep Research: Institutional Pattern Intelligence v3.2

**Status:** research architecture for the Pine indicator and downstream validation stack.  
**Objective:** search for a sparse, high-expectancy setup family capable of sustaining unusually high win rate at high reward/risk **without assuming that target performance exists**.

## 1. Executive conclusion

The indicator should not be optimized as a collection of named chart patterns. The most defensible architecture is:

1. **Deterministic event ontology** — confirmed swings, trend state, liquidity events, structural breaks, displacement, FVG/IFVG, OB mitigation, OTE, external-liquidity targets.
2. **Context buckets** — structure, liquidity/momentum, PD-array location, MTF narrative, regime/session quality, and projected R. Correlated observations are capped inside buckets so five versions of the same fact cannot manufacture a 95% score.
3. **Sparse candidate generation** — reversal and continuation are separate families.
4. **Unbiased research export** — export pre-A+ candidates as well as winners; otherwise the calibration dataset is selection-biased.
5. **External enrichment** — real L2/order-flow/CVD/funding/open-interest data belong outside Pine. Pine's candle-location volume proxy is not equivalent to order-flow imbalance.
6. **Outcome labeling** — first-touch barriers, MFE/MAE, DOL hit, time-to-target and regime transitions.
7. **Chronological validation** — walk-forward, overlapping-event purge, embargo, realistic costs, parameter freeze.
8. **Meta-decision layer** — Jev may judge a compact prepared state, but deterministic code owns thresholds, hard vetoes, sizing and execution.

This makes ICT/SMC language an **operational ontology of hypotheses**, not assumed causal truth.

---

## 2. What the literature supports

### 2.1 Systematic chart-pattern recognition can contain incremental information

Lo, Mamaysky and Wang formalized technical pattern recognition with nonparametric methods and found that several patterns changed conditional return distributions relative to unconditional returns. The important lesson is not that every named pattern is profitable; it is that subjective visual structures can be converted into reproducible algorithms and tested statistically.

**Design implication:** classical geometry stays in the indicator, but as a measured feature. It should not override the structural/liquidity execution state.

Source: Andrew W. Lo, Harry Mamaysky, Jiang Wang, *Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation*, Journal of Finance / NBER Working Paper 7613.  
https://www.nber.org/papers/w7613

### 2.2 Trend / time-series momentum is one of the stronger cross-market priors

Moskowitz, Ooi and Pedersen documented time-series momentum across equity index, currency, commodity and bond futures, with return persistence over intermediate horizons. Hurst, Ooi and Pedersen extended trend-following evidence over a much longer historical sample.

**Design implication:** continuation trades deserve their own family. Hidden divergence, coil/pullback, BOS, PD-array re-entry and MTF trend agreement should be evaluated differently from reversal sweeps.

Sources:  
https://doi.org/10.1016/j.jfineco.2011.11.003  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026

### 2.3 Short-horizon price formation is strongly linked to order-flow imbalance

Cont, Kukanov and Stoikov found that short-horizon price changes are closely related to order-flow imbalance and market depth. More recent crypto research supports testing order flow, while also showing that apparent short-horizon predictability can be unstable as samples grow.

**Design implication:** Pine's volume/candle-position proxy is only a weak context vote. A serious live stack should enrich candidate alerts with venue-native L2 OFI, CVD/aggressor flow, spread, depth, funding/open interest and execution costs before meta-labeling or Jev adjudication.

Sources:  
https://arxiv.org/abs/1011.6402  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7227998  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5020002

### 2.4 Volatility should affect risk, not merely direction

Moreira and Muir show that scaling risk down when volatility is high can improve risk-adjusted performance for several factor portfolios. This does not directly prove an intraday entry edge, but it supports separating **signal quality** from **risk allocation**.

**Design implication:** the indicator detects regimes; the eventual strategy engine should size separately using volatility and loss-state constraints. Do not let a strong setup score automatically imply maximum size.

Source: Alan Moreira and Tyler Muir, *Volatility-Managed Portfolios*.  
https://www.nber.org/papers/w22208

### 2.5 Intraday seasonality is real, but “killzones” must be tested asset-by-asset

Intraday volume, volatility and return characteristics vary materially by time of day in equities, FX and futures. That supports session conditioning, but it does not validate any specific ICT clock window universally.

**Design implication:** London/NY windows are categorical features and potential gates, not axioms. Their incremental value must survive asset/timeframe ablation.

Examples:  
https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID998470_code251135.pdf?abstractid=998470  
https://papers.ssrn.com/sol3/Delivery.cfm/6415578.pdf?abstractid=6415578

### 2.6 Hidden RSI divergence has much weaker evidence than trend or microstructure

There is limited empirical work on hidden divergence. A 2024 study on the Indonesian Sharia Stock Index reports predictive utility, but this is one market/sample and is not enough to treat hidden divergence as a universal edge.

**Design implication:** hidden divergence is a low-weight continuation feature, exactly as v3.2 now treats it. It should earn or lose weight from our own OOS data.

Source:  
https://jurnal.unismabekasi.ac.id/index.php/jrak/article/view/7935

---

## 3. What is *not* established

There is no broad academic evidence that concepts labelled FVG, order block, liquidity sweep, OTE, SMT, CHOCH or BOS — as used in retail ICT/SMC discourse — independently produce a stable edge across markets and regimes.

That does **not** make them useless. Many are machine-readable descriptions of:

- local extrema and failed breakout/reclaim behavior,
- imbalance / rapid displacement,
- retracement location,
- cross-market disagreement,
- range compression and expansion,
- likely resting-liquidity reference points.

The correct scientific treatment is therefore: **encode them precisely, then test their incremental conditional value**.

A feature survives only if it improves OOS economics after costs and remains useful across folds/regimes. Naming a market behavior is not proof that the behavior predicts returns.

---

## 4. Why the new grouped score matters

The previous additive score could double-count correlated evidence. Example:

- sweep,
- CHOCH,
- displacement,
- FVG,
- ordered lifecycle

are not five independent observations; they often arise from the same price path.

v3.2 therefore creates capped research buckets:

| Bucket | Reversal role | Continuation role |
|---|---|---|
| Structure | ordered sweep → MSS/CHOCH → displacement/FVG | BOS → displacement/FVG |
| Liquidity / momentum | sweep, SMT, regular divergence | hidden divergence, SMT, coil |
| PD array | FVG, IFVG, OB, OTE | FVG, IFVG, OB, OTE |
| Narrative | HTF + 5/15/60 + macro + session | same |
| Quality | volume, flow proxy, regime, divergence, entry touch | same |
| RR | DOL-based projected R | DOL-based projected R |

This does not magically create probability calibration. It produces a **less pathological ordinal score** that can later be calibrated to observed outcomes.

---

## 5. Core falsifiable hypotheses

### H1 — Ordered reversal lifecycle
A sell-side sweep followed by bullish MSS/CHOCH, displacement and FVG creation, then retracement into a PD array, has higher 6R-before-stop probability than the same PD-array touch without the ordered lifecycle. Mirror for shorts.

### H2 — Continuation is a different conditional distribution
HTF/MTF trend + BOS + compression/pullback + PD-array re-entry should outperform treating the same setup as a generic reversal. Hidden divergence should contribute more here than regular divergence.

### H3 — SMT adds incremental information only in context
SMT should be tested conditionally on liquidity event + structure, not as a standalone trigger. Test one-reference and two-reference versions separately.

### H4 — 5/15/60 agreement improves selectivity
2/3 or 3/3 alignment may increase win rate but can reduce frequency and worsen entry price. Evaluate expectancy and 6R hit rate, not win rate alone.

### H5 — Coinlegs / macro alignment is asset-class dependent
BTC alignment may help altcoin continuation; DXY-like inverse alignment may help FX/metals. The same macro reference should not be assumed across all symbols.

### H6 — PD-array stacking is useful only up to a point
FVG + IFVG + OB + OTE overlap may improve location quality, but correlated PD-array features may saturate. Bucket caps prevent score inflation; ablation tests measure real incremental value.

### H7 — DOL geometry is central to high-R feasibility
A beautiful setup with only 2R to the nearest plausible external liquidity is not a 6R setup. Projected R must be evaluated at candidate creation, with target definitions frozen before outcome observation.

### H8 — Real order flow should dominate candle-volume proxies at very short horizons
When L2/CVD/depth data are available, compare them directly against the Pine flow proxy. The proxy survives only if it adds value after real microstructure features enter the model.

---

## 6. The 80% WR / 6R target: statistical reality

A system that truly wins 80% of trades at +6R and loses 20% at -1R has arithmetic expectancy of **+4.6R/trade before costs**. That is extraordinary. The correct response is not to lower ambition; it is to raise the evidence standard.

If 300 **independent** OOS trades produce exactly 80% wins, the approximate two-sided 95% Wilson interval is about **75.1%–84.1%**. At 100 trades the interval is much wider, roughly **71.1%–86.7%**. Overlapping or clustered signals reduce effective sample size, so trade count alone overstates certainty.

Therefore the repo must not claim “80% WR” from a small backtest or from repeated parameter search.

---

## 7. Backtest-overfitting controls

Bailey, López de Prado and collaborators show why repeated backtest optimization inflates apparent Sharpe/performance. Sullivan, Timmermann and White demonstrate the same issue in technical-rule testing: the best in-sample rule can fail in the subsequent period after data-snooping correction.

**Required controls:**

- chronological train / validation / test separation;
- no random shuffling of time-series events;
- purge overlapping outcome windows from fold boundaries;
- embargo after train folds when labels overlap into the future;
- record every parameter/configuration trial;
- freeze the final rule before the untouched test;
- report all costs and slippage assumptions;
- compute uncertainty on win rate and expectancy;
- use block bootstrap because trades cluster;
- monitor Probability of Backtest Overfitting / Deflated Sharpe when comparing many variants;
- do not call label accuracy “strategy performance.”

Sources:  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253  
https://doi.org/10.3905/jpm.2014.40.5.094  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=160330  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7177958

---

## 8. Jev: where it is useful

The strongest architecture is consistent with the public Jev trading implementations:

> deterministic code computes state → Jev judges a narrow question → deterministic policy applies thresholds/vetoes → execution remains separate.

Jev should **not** receive raw chart screenshots and invent trades. It should receive a compact state such as:

- family: reversal / continuation,
- grouped score buckets,
- projected R,
- 5/15/60 votes,
- structure lifecycle state,
- SMT/divergence state,
- PD-array state,
- regime/session,
- external microstructure enrichment: spread, L2 OFI, depth, CVD, recent returns, funding/OI when applicable,
- allowed actions including **abstain**.

Use atomic judgments rather than a single “should I trade?” prompt. Example judgments:

1. direction: up / down / unclear;
2. follow-through: continuation / reversal / no-pattern;
3. setup quality: low / medium / high / exceptional;
4. liquidity safe: yes / no;
5. toxic flow: yes / no;
6. execution environment: favorable / marginal / avoid.

Then calibrate probabilities on our own venue using Brier score, log loss, expected calibration error and reliability curves. Hard risk limits never go into model control.

Sources:  
https://github.com/buberlo/jev-trader  
https://jev-trader.com/faq/jev-trading  
https://jev-trader.com/faq/jev-ai-decision-model

---

## 9. v3.2 research loop

1. Turn on `Export Research Candidates` in Pine.
2. Use a TradingView alert on `Any alert() function call` to a collector.
3. Save JSONL exactly as received.
4. Enrich externally with spread / fees / slippage / L2 / CVD / funding / OI where available.
5. Label candidates with `research/label_candidates.py` against clean OHLCV.
6. Run `research/validate.py`.
7. Compare reversal vs continuation, score buckets, assets, timeframes and A+ vs pre-A+ candidates.
8. Run ablations one feature family at a time.
9. Freeze weights before final OOS.
10. Only after calibration, enable Jev gating and compare **Pine-only vs Pine+Jev** on identical frozen candidates.

---

## 10. Priority research order

1. **Outcome-label integrity and costs** — a bad label invalidates everything.
2. **Reversal vs continuation separation.**
3. **Ordered lifecycle ablation.**
4. **PD-array location ablation.**
5. **5/15/60 alignment.**
6. **SMT / regular / hidden divergence incremental value.**
7. **Session effects by asset.**
8. **Coinlegs/macro relation by asset.**
9. **Real L2 OFI/CVD enrichment.**
10. **Jev calibration and policy thresholds.**

The target is not “more confluence.” The target is the **smallest stable feature set that preserves OOS expectancy**.
