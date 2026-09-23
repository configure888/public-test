#!/usr/bin/env python3
"""Append-only registry for every strategy/model experiment.

The point is trial accounting: discarded configurations still count. A backtest that is not
registered should not be used in a performance claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()


def git_sha() -> str:
    try:
        return subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    except Exception:
        return "unknown"


def canonical(x: Any) -> str:
    return json.dumps(x,separators=(",",":"),sort_keys=True)


def read_registry(path: Path) -> list[dict]:
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def register(args) -> None:
    config=json.loads(args.config.read_text(encoding="utf-8"))
    data={str(p):sha256_file(p) for p in args.data}
    code=args.git_sha or git_sha()
    fingerprint=hashlib.sha256(canonical({"config":config,"data":data,"git_sha":code}).encode()).hexdigest()
    rows=read_registry(args.registry)
    duplicate=next((r for r in rows if r["fingerprint"]==fingerprint),None)
    if duplicate:
        print(json.dumps({"duplicate":True,"trial_id":duplicate["trial_id"],"fingerprint":fingerprint}))
        return
    trial_id=fingerprint[:16]
    rec={
        "trial_id":trial_id,"fingerprint":fingerprint,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "git_sha":code,"config":config,"data_sha256":data,
        "metrics":json.loads(args.metrics.read_text(encoding="utf-8")) if args.metrics else None,
        "note":args.note,
    }
    args.registry.parent.mkdir(parents=True,exist_ok=True)
    with args.registry.open("a",encoding="utf-8") as f:f.write(canonical(rec)+"\n")
    print(json.dumps({"duplicate":False,"trial_id":trial_id,"trial_number":len(rows)+1,"fingerprint":fingerprint}))


def summary(args) -> None:
    rows=read_registry(args.registry)
    print(json.dumps({"registered_trials":len(rows),"unique_fingerprints":len({r["fingerprint"] for r in rows}),
                      "first":rows[0]["created_at"] if rows else None,"last":rows[-1]["created_at"] if rows else None},indent=2))


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    r=sub.add_parser("register")
    r.add_argument("--registry",type=Path,default=Path("experiments/trials.jsonl"))
    r.add_argument("--config",required=True,type=Path)
    r.add_argument("--data",type=Path,nargs="+",required=True)
    r.add_argument("--metrics",type=Path)
    r.add_argument("--git-sha")
    r.add_argument("--note",default="")
    r.set_defaults(fn=register)
    s=sub.add_parser("summary")
    s.add_argument("--registry",type=Path,default=Path("experiments/trials.jsonl"))
    s.set_defaults(fn=summary)
    args=ap.parse_args(); args.fn(args)


if __name__=="__main__":
    main()
