#!/usr/bin/env python3
"""Download public OHLCV for outcome labeling.

Binance USD-M uses /fapi/v1/klines.
Hyperliquid uses info:candleSnapshot (only the recent history retained by the venue is available).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path

import httpx


def ts_ms(v: str) -> int:
    try:
        x = float(v)
        return int(x if x > 10_000_000_000 else x * 1000)
    except ValueError:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)


def hl_coin(symbol: str) -> str:
    s = symbol.split(":")[-1].upper().replace("/", "").replace("-", "")
    for suffix in ("USDT","USDC","USD"):
        if s.endswith(suffix) and len(s) > len(suffix):
            return s[:-len(suffix)]
    return s


async def binance(symbol: str, interval: str, start: int, end: int) -> list[list]:
    symbol = symbol.split(":")[-1].upper().replace("/", "").replace("-", "")
    rows = []
    cursor = start
    async with httpx.AsyncClient(base_url="https://fapi.binance.com", timeout=15) as client:
        while cursor <= end:
            r = await client.get("/fapi/v1/klines", params={"symbol":symbol,"interval":interval,"startTime":cursor,"endTime":end,"limit":1500})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for x in batch:
                rows.append([int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])])
            nxt = int(batch[-1][6]) + 1
            if nxt <= cursor:
                break
            cursor = nxt
    return rows


async def hyperliquid(symbol: str, interval: str, start: int, end: int) -> list[list]:
    coin = hl_coin(symbol)
    rows = []
    cursor = start
    async with httpx.AsyncClient(timeout=15) as client:
        while cursor <= end:
            r = await client.post("https://api.hyperliquid.xyz/info", json={"type":"candleSnapshot","req":{"coin":coin,"interval":interval,"startTime":cursor,"endTime":end}})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for x in batch:
                rows.append([int(x["t"]), float(x["o"]), float(x["h"]), float(x["l"]), float(x["c"]), float(x["v"])])
            nxt = int(batch[-1]["T"]) + 1
            if nxt <= cursor:
                break
            cursor = nxt
            if len(batch) < 2:
                break
    # De-duplicate venue pagination boundaries.
    dedup = {r[0]: r for r in rows}
    return [dedup[k] for k in sorted(dedup)]


async def main_async(args) -> None:
    start, end = ts_ms(args.start), ts_ms(args.end)
    if args.venue == "binance":
        rows = await binance(args.symbol, args.interval, start, end)
    else:
        rows = await hyperliquid(args.symbol, args.interval, start, end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp","open","high","low","close","volume"])
        w.writerows(rows)
    print(f"venue={args.venue} symbol={args.symbol} interval={args.interval} rows={len(rows)} out={args.out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=["binance","hyperliquid"], required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--start", required=True, help="ISO-8601 or unix seconds/ms")
    ap.add_argument("--end", required=True, help="ISO-8601 or unix seconds/ms")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
