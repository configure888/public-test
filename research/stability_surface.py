#!/usr/bin/env python3
"""Generate score/R threshold stability surfaces from an already frozen labeled dataset.

This does not select a winner. It exposes whether performance lives on a broad plateau or a
single fragile threshold combination.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def truth(v: str) -> bool:
    return str(v).strip().lower() in {"1","true","yes"}


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float,float]:
    if not n:
        return float("nan"), float("nan")
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d
    h=z*((p*(1-p)/n+z*z/(4*n*n))**0.5)/d
    return c-h,c+h


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--score-min", type=int, default=40)
    ap.add_argument("--score-max", type=int, default=90)
    ap.add_argument("--score-step", type=int, default=5)
    ap.add_argument("--rr-min", type=float, default=2)
    ap.add_argument("--rr-max", type=float, default=8)
    ap.add_argument("--rr-step", type=float, default=1)
    args=ap.parse_args()

    with args.data.open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    rows=[r for r in rows if r.get("six_r_before_stop","")!="" and r.get("grouped_score","")!="" and r.get("rr","")!=""]

    out=[]
    s=args.score_min
    while s <= args.score_max:
        rr=args.rr_min
        while rr <= args.rr_max+1e-9:
            sample=[r for r in rows if float(r["grouped_score"])>=s and float(r["rr"])>=rr]
            n=len(sample); k=sum(truth(r["six_r_before_stop"]) for r in sample)
            lo,hi=wilson(k,n)
            contract=[float(r["contract_r"]) for r in sample if r.get("contract_r","") not in ("",None)]
            out.append({
                "score_threshold":s,"rr_threshold":rr,"n":n,
                "win_rate_6r":k/n if n else "",
                "wilson95_low":lo if n else "","wilson95_high":hi if n else "",
                "mean_contract_r":sum(contract)/len(contract) if contract else "",
            })
            rr+=args.rr_step
        s+=args.score_step

    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()) if out else ["score_threshold"])
        w.writeheader(); w.writerows(out)
    print(json.dumps({"rows":len(rows),"surface_cells":len(out),"out":str(args.out)}))


if __name__=="__main__":
    main()
