#!/usr/bin/env python3
"""Chronological meta-label training for 6R-before-stop.

The untouched final 20% is used once for reporting. Model selection/calibration uses only
train + validation. This is deliberately smaller and easier to audit than the live strategy.
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score


CATEGORICAL = ["side", "family", "symbol", "tf", "micro_venue"]
NUMERIC = [
    "grouped_score","legacy_score","rr","structure_bucket","liquidity_bucket","pd_bucket",
    "narrative_bucket","quality_bucket","rr_bucket","mtf_votes","sweep","smt","regular_div",
    "hidden_div","fvg","ifvg","ob","ote","coil","killzone","vwap_z",
    "micro_capture_distance_ms","micro_stale","micro_spread_bps","micro_microprice_edge_bps",
    "micro_book_imbalance_5","micro_book_imbalance_10","micro_book_imbalance_20",
    "micro_trade_count","micro_trade_imbalance","micro_cvd_qty","micro_cvd_notional",
    "micro_buy_notional_ratio","micro_trade_window_ms","micro_basis_bps","micro_funding_rate",
    "micro_open_interest","micro_day_notional_volume",
]


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    eps = 1e-6
    p = np.clip(p, eps, 1-eps)
    out = {
        "n": int(len(y)),
        "positive_rate": float(np.mean(y)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0,1])),
    }
    out["roc_auc"] = float(roc_auc_score(y, p)) if len(set(y.tolist())) > 1 else None
    return out


def threshold_table(y: np.ndarray, p: np.ndarray) -> list[dict]:
    out = []
    for t in (0.50,0.60,0.65,0.70,0.75,0.80,0.85,0.90):
        mask = p >= t
        n = int(mask.sum())
        if n:
            wr = float(y[mask].mean())
            expectancy = wr * 6.0 - (1.0-wr)
        else:
            wr = expectancy = None
        out.append({"threshold":t,"accepted":n,"acceptance_rate":n/len(y) if len(y) else 0.0,"win_rate_6r":wr,"binary_6r_expectancy":expectancy})
    return out


def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    cols = [c for c in NUMERIC + CATEGORICAL if c in df.columns]
    x = df[cols].copy()
    for c in [c for c in NUMERIC if c in x.columns]:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    for c in [c for c in CATEGORICAL if c in x.columns]:
        x[c] = x[c].fillna("NA").astype(str)
    x = pd.get_dummies(x, columns=[c for c in CATEGORICAL if c in x.columns], dummy_na=False, dtype=float)
    x = x.replace([np.inf,-np.inf], np.nan)
    med = x.median(numeric_only=True)
    x = x.fillna(med).fillna(0.0)
    return x.astype(float), list(x.columns)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--min-rows", type=int, default=300)
    args = ap.parse_args()

    df = pd.read_csv(args.data).sort_values(["time","received_ms"], kind="stable")
    df = df[df["six_r_before_stop"].notna()].reset_index(drop=True)
    if len(df) < args.min_rows:
        raise SystemExit(f"need at least {args.min_rows} labeled rows; got {len(df)}")

    y = df["six_r_before_stop"].astype(int).to_numpy()
    x, columns = prepare(df)
    n = len(df)
    i1, i2 = int(n*0.60), int(n*0.80)
    if min(i1, i2-i1, n-i2) < 30:
        raise SystemExit("chronological folds too small")
    xt, xv, xte = x.iloc[:i1], x.iloc[i1:i2], x.iloc[i2:]
    yt, yv, yte = y[:i1], y[i1:i2], y[i2:]

    candidates = {
        "logistic": LogisticRegression(max_iter=3000, class_weight="balanced", C=0.25),
        "hist_gb": HistGradientBoostingClassifier(max_iter=200, learning_rate=0.04, max_leaf_nodes=15, l2_regularization=2.0),
    }
    fitted = {}
    validation = {}
    for name, model in candidates.items():
        model.fit(xt, yt)
        raw = model.predict_proba(xv)[:,1]
        iso = IsotonicRegression(out_of_bounds="clip").fit(raw, yv)
        cal = iso.predict(raw)
        fitted[name] = (model, iso)
        validation[name] = metrics(yv, cal)

    winner = min(validation, key=lambda k: validation[k]["brier"])
    model, iso = fitted[winner]
    raw_test = model.predict_proba(xte)[:,1]
    p_test = iso.predict(raw_test)

    report = {
        "rows": n,
        "splits": {"train":i1,"validation":i2-i1,"test":n-i2},
        "feature_count": len(columns),
        "selected_model": winner,
        "validation": validation,
        "untouched_test": metrics(yte, p_test),
        "test_thresholds": threshold_table(yte, p_test),
        "warning": "Do not tune against untouched_test. Any change after reading test results requires a new future holdout.",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir/"meta_report.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    with (args.out_dir/"meta_model.pkl").open("wb") as f:
        pickle.dump({"model":model,"calibrator":iso,"columns":columns,"selected_model":winner}, f)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
