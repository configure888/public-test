#!/usr/bin/env python3
"""Simple conditional ablation table for boolean setup features.

Use this before complex ML: if a feature cannot show stable incremental value by fold/regime,
it should not receive a large hand-authored score.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FEATURES=["sweep","smt","regular_div","hidden_div","fvg","ifvg","ob","ote","coil","killzone","a_plus"]


def truth(v) -> bool:
    return str(v).strip().lower() in {"1","true","yes"}


def stats(rows):
    n=len(rows)
    if not n:return {"n":0,"win_rate_6r":None,"mean_contract_r":None}
    wins=sum(truth(r["six_r_before_stop"]) for r in rows)
    vals=[float(r["contract_r"]) for r in rows if r.get("contract_r","")!=""]
    return {"n":n,"win_rate_6r":wins/n,"mean_contract_r":sum(vals)/len(vals) if vals else None}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",required=True,type=Path)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    with args.data.open(newline="",encoding="utf-8") as f:
        rows=[r for r in csv.DictReader(f) if r.get("six_r_before_stop","")!=""]
    report={}
    for feat in FEATURES:
        if not rows or feat not in rows[0]: continue
        on=[r for r in rows if truth(r.get(feat))]
        off=[r for r in rows if not truth(r.get(feat))]
        a,b=stats(on),stats(off)
        report[feat]={"on":a,"off":b,
            "delta_win_rate":(a["win_rate_6r"]-b["win_rate_6r"]) if a["win_rate_6r"] is not None and b["win_rate_6r"] is not None else None,
            "delta_mean_r":(a["mean_contract_r"]-b["mean_contract_r"]) if a["mean_contract_r"] is not None and b["mean_contract_r"] is not None else None}
    txt=json.dumps(report,indent=2,sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(txt+"\n",encoding="utf-8")
    print(txt)


if __name__=="__main__":
    main()
