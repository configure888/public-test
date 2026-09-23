#!/usr/bin/env python3
"""Validate labeled candidate events without third-party dependencies.

Reports the quantities that matter for this project: 6R-before-stop win rate,
Wilson uncertainty, expectancy in R, drawdown, MFE/MAE, chronological fold
stability, score-bucket monotonicity, and block-bootstrap confidence intervals.
"""

from __future__ import annotations
import argparse, json, math, random, statistics
from collections import defaultdict
from pathlib import Path


def load(path: Path) -> list[dict]:
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        x=json.loads(line)
        if "label_error" not in x and "six_r_before_stop" in x:
            rows.append(x)
    rows.sort(key=lambda x:int(x.get("time",0)))
    return rows


def wilson(k:int,n:int,z:float=1.959963984540054)->tuple[float,float]:
    if n==0:return (float("nan"),float("nan"))
    p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return c-h,c+h


def max_drawdown(rs:list[float])->float:
    eq=0.0; peak=0.0; dd=0.0
    for r in rs:
        eq+=r; peak=max(peak,eq); dd=max(dd,peak-eq)
    return dd


def summary(rows:list[dict])->dict:
    n=len(rows)
    if not n:return {"n":0}
    wins=sum(bool(x["six_r_before_stop"]) for x in rows)
    vals=[float(x["contract_r"]) for x in rows]
    mfe=[float(x["mfe_r"]) for x in rows]
    mae=[float(x["mae_r"]) for x in rows]
    lo,hi=wilson(wins,n)
    return {
        "n":n,"wins_6r":wins,"win_rate_6r":wins/n,"wilson95_low":lo,"wilson95_high":hi,
        "expectancy_r":statistics.fmean(vals),"median_r":statistics.median(vals),
        "mfe_r_mean":statistics.fmean(mfe),"mae_r_mean":statistics.fmean(mae),
        "max_drawdown_r":max_drawdown(vals),
    }


def block_bootstrap(rows:list[dict],iterations:int,block:int,seed:int)->dict:
    if not rows:return {}
    rng=random.Random(seed); n=len(rows); metrics=[]
    for _ in range(iterations):
        sample=[]
        while len(sample)<n:
            start=rng.randrange(n)
            for j in range(block):
                sample.append(rows[(start+j)%n])
                if len(sample)>=n:break
        s=summary(sample); metrics.append((s["win_rate_6r"],s["expectancy_r"]))
    metrics.sort()
    wr=sorted(x[0] for x in metrics); ex=sorted(x[1] for x in metrics)
    def q(a,p): return a[min(len(a)-1,max(0,int(round((len(a)-1)*p))))]
    return {"iterations":iterations,"block":block,"win_rate_ci95":[q(wr,.025),q(wr,.975)],"expectancy_r_ci95":[q(ex,.025),q(ex,.975)]}


def grouped(rows:list[dict],key:str)->dict:
    d=defaultdict(list)
    for x in rows:d[str(x.get(key,"NA"))].append(x)
    return {k:summary(v) for k,v in sorted(d.items())}


def score_bucket(x:dict)->str:
    s=float(x.get("grouped_score",0)); lo=int(s//10)*10
    return f"{lo:02d}-{lo+9:02d}"


def folds(rows:list[dict],nfold:int)->list[dict]:
    out=[]
    for i in range(nfold):
        a=round(i*len(rows)/nfold); b=round((i+1)*len(rows)/nfold)
        out.append({"fold":i+1,"start":a,"end":b,**summary(rows[a:b])})
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--labeled",required=True,type=Path)
    ap.add_argument("--out",type=Path)
    ap.add_argument("--folds",type=int,default=5)
    ap.add_argument("--bootstrap",type=int,default=2000)
    ap.add_argument("--block",type=int,default=10)
    ap.add_argument("--seed",type=int,default=7)
    args=ap.parse_args()
    rows=load(args.labeled)
    buckets=defaultdict(list)
    for x in rows:buckets[score_bucket(x)].append(x)
    report={
        "overall":summary(rows),
        "by_family":grouped(rows,"family"),
        "by_symbol":grouped(rows,"symbol"),
        "by_timeframe":grouped(rows,"tf"),
        "by_a_plus":grouped(rows,"a_plus"),
        "by_grouped_score_bucket":{k:summary(v) for k,v in sorted(buckets.items())},
        "chronological_folds":folds(rows,args.folds) if rows else [],
        "block_bootstrap":block_bootstrap(rows,args.bootstrap,args.block,args.seed),
        "claim_guard":{
            "observed_80pct_independent_trades_needed_for_wilson95_lower_above_75pct":"about 300",
            "note":"Clustered/overlapping trades reduce effective sample size; do not treat this as a guarantee or a substitute for OOS testing."
        }
    }
    txt=json.dumps(report,indent=2,sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(txt+"\n",encoding="utf-8")
    print(txt)

if __name__=="__main__": main()
