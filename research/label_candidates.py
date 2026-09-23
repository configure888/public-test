#!/usr/bin/env python3
"""Label exported TradingView research candidates against OHLCV bars.

Input candidates: JSONL emitted by indicator.pine (`type=research_candidate`).
Input OHLCV CSV: timestamp,open,high,low,close[,volume]
Timestamp may be Unix milliseconds or an ISO-8601 string.

For each event the script evaluates first-touch barriers in R-space, using a
conservative rule when stop and target are both touched in the same bar: stop
wins. This prevents optimistic intrabar sequencing assumptions.
"""

from __future__ import annotations
import argparse, csv, json, math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def ts_ms(value: str | int | float) -> int:
    if isinstance(value, (int, float)):
        x = float(value)
        return int(x if x > 10_000_000_000 else x * 1000)
    s = str(value).strip()
    try:
        x = float(s)
        return int(x if x > 10_000_000_000 else x * 1000)
    except ValueError:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)


@dataclass
class Bar:
    t: int
    o: float
    h: float
    l: float
    c: float


def load_bars(path: Path) -> list[Bar]:
    out: list[Bar] = []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close"}
        missing = required - set(r.fieldnames or [])
        if missing:
            raise SystemExit(f"OHLCV missing columns: {sorted(missing)}")
        for row in r:
            out.append(Bar(ts_ms(row["timestamp"]), float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])))
    out.sort(key=lambda x: x.t)
    return out


def load_candidates(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") != "research_candidate":
                continue
            obj["_line"] = line_no
            out.append(obj)
    return out


def first_index_ge(bars: list[Bar], t: int) -> int:
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].t < t:
            lo = mid + 1
        else:
            hi = mid
    return lo


def label_one(ev: dict, bars: list[Bar], horizon: int, multiples: list[float]) -> dict:
    side = ev["side"].lower()
    entry = float(ev["entry"])
    stop = float(ev["stop"])
    if side not in {"long", "short"}:
        raise ValueError(f"bad side: {side}")
    risk = entry - stop if side == "long" else stop - entry
    if not math.isfinite(risk) or risk <= 0:
        return {**ev, "label_error": "nonpositive_risk"}

    start = first_index_ge(bars, int(ev["time"]))
    if start >= len(bars):
        return {**ev, "label_error": "no_bars_after_event"}
    sample = bars[start : min(len(bars), start + horizon)]
    if not sample:
        return {**ev, "label_error": "empty_horizon"}

    mfe_r = 0.0
    mae_r = 0.0
    first_hit = {f"hit_{m:g}r_bar": None for m in multiples}
    stop_bar = None
    dol_bar = None
    target = ev.get("target")
    target = float(target) if target is not None and str(target).lower() not in {"na", "nan", ""} else None

    for j, b in enumerate(sample):
        fav = (b.h - entry) / risk if side == "long" else (entry - b.l) / risk
        adv = (entry - b.l) / risk if side == "long" else (b.h - entry) / risk
        mfe_r = max(mfe_r, fav)
        mae_r = max(mae_r, adv)

        stop_touched = b.l <= stop if side == "long" else b.h >= stop
        # Conservative same-bar rule: stop first.
        if stop_bar is None and stop_touched:
            stop_bar = j

        for m in multiples:
            key = f"hit_{m:g}r_bar"
            if first_hit[key] is None:
                px = entry + m * risk if side == "long" else entry - m * risk
                touched = b.h >= px if side == "long" else b.l <= px
                if touched:
                    first_hit[key] = j

        if target is not None and dol_bar is None:
            touched = b.h >= target if side == "long" else b.l <= target
            if touched:
                dol_bar = j

    six_key = "hit_6r_bar"
    six_bar = first_hit.get(six_key)
    if six_bar is not None and stop_bar is not None and six_bar == stop_bar:
        six_before_stop = False
    else:
        six_before_stop = six_bar is not None and (stop_bar is None or six_bar < stop_bar)

    last = sample[-1].c
    terminal_r = (last - entry) / risk if side == "long" else (entry - last) / risk
    realized_contract_r = 6.0 if six_before_stop else (-1.0 if stop_bar is not None and (six_bar is None or stop_bar <= six_bar) else terminal_r)

    return {
        **ev,
        "risk_abs": risk,
        "horizon_bars": len(sample),
        "mfe_r": round(mfe_r, 6),
        "mae_r": round(mae_r, 6),
        "stop_bar": stop_bar,
        **first_hit,
        "six_r_before_stop": six_before_stop,
        "dol_hit_bar": dol_bar,
        "terminal_r": round(terminal_r, 6),
        "contract_r": round(realized_contract_r, 6),
        "event_end_ms": sample[-1].t,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--ohlcv", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--horizon", type=int, default=100)
    ap.add_argument("--multiples", default="1,2,3,4,6,8,10")
    args = ap.parse_args()
    multiples = sorted({float(x) for x in args.multiples.split(",") if x.strip()})
    bars = load_bars(args.ohlcv)
    events = load_candidates(args.candidates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(label_one(ev, bars, args.horizon, multiples), separators=(",", ":")) + "\n")
    print(f"labeled={len(events)} bars={len(bars)} out={args.out}")


if __name__ == "__main__":
    main()
