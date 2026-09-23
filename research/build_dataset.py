#!/usr/bin/env python3
"""Join Pine candidates, live microstructure enrichment, Jev decisions and outcome labels."""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any


PAYLOAD_FIELDS = [
    "time","symbol","tf","side","family","grouped_score","legacy_score","score","rr",
    "structure_bucket","liquidity_bucket","pd_bucket","narrative_bucket","quality_bucket","rr_bucket",
    "mtf_votes","sweep","smt","regular_div","hidden_div","fvg","ifvg","ob","ote","coil","killzone","vwap_z","a_plus",
]
MICRO_FIELDS = [
    "venue","ts_ms","snapshot_distance_ms","capture_distance_ms","stale",
    "mid","spread_bps","microprice_edge_bps",
    "bid_depth_5","ask_depth_5","book_imbalance_5",
    "bid_depth_10","ask_depth_10","book_imbalance_10",
    "bid_depth_20","ask_depth_20","book_imbalance_20",
    "trade_count","taker_buy_qty","taker_sell_qty","trade_imbalance","cvd_qty",
    "taker_buy_notional","taker_sell_notional","cvd_notional","buy_notional_ratio","trade_window_ms",
    "mark_price","index_price","oracle_price","basis_bps","funding_rate","open_interest","day_notional_volume","premium",
]
LABEL_FIELDS = [
    "six_r_before_stop","contract_r","mfe_r","mae_r","stop_bar","hit_1r_bar","hit_2r_bar","hit_3r_bar",
    "hit_4r_bar","hit_6r_bar","hit_8r_bar","hit_10r_bar","dol_hit_bar","terminal_r",
]


def load_labels(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        x = json.loads(line)
        if x.get("event_id"):
            out[str(x["event_id"])] = x
    return out


def scalar(v: Any) -> Any:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(",", ":"), sort_keys=True)
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--labels", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    labels = load_labels(args.labels)
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT e.*, j.action AS jev_action, j.payload_json AS jev_payload,
                  s.status AS shadow_status, s.realized_r AS shadow_realized_r
           FROM events e
           LEFT JOIN jev_decisions j ON j.event_id=e.event_id
           LEFT JOIN shadow_trades s ON s.event_id=e.event_id
           ORDER BY e.received_ms"""
    ).fetchall()

    out_rows: list[dict[str, Any]] = []
    for row in rows:
        p = json.loads(row["payload_json"])
        m = json.loads(row["enrichment_json"]) if row["enrichment_json"] else {}
        x: dict[str, Any] = {
            "event_id": row["event_id"],
            "received_ms": row["received_ms"],
            "enrichment_ts_ms": row["enrichment_ts_ms"],
            "event_status": row["status"],
            "jev_action": row["jev_action"],
            "shadow_status": row["shadow_status"],
            "shadow_realized_r": row["shadow_realized_r"],
        }
        for k in PAYLOAD_FIELDS:
            x[k] = scalar(p.get(k))
        for k in MICRO_FIELDS:
            x[f"micro_{k}"] = scalar(m.get(k))
        lab = labels.get(row["event_id"], {})
        for k in LABEL_FIELDS:
            x[k] = scalar(lab.get(k))
        out_rows.append(x)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(out_rows[0].keys()) if out_rows else ["event_id"]
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)
    print(f"rows={len(out_rows)} out={args.out}")


if __name__ == "__main__":
    main()
