from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from typing import Any

import websockets

from config import settings
from features import merge_snapshot
from storage import Store
from venues import BinanceUSDm, Hyperliquid, normalize_binance_symbol, normalize_hyperliquid_coin

store = Store(settings.db_path)
TRADE_WINDOW_MS = int(os.getenv("TRADE_WINDOW_MS", "30000"))
CONTEXT_REFRESH_MS = int(os.getenv("CONTEXT_REFRESH_MS", "30000"))


def _prune(q: deque[dict[str, Any]], now_ms: int) -> None:
    while q:
        t = int(q[0].get("T", q[0].get("time", 0)) or 0)
        if now_ms - t <= TRADE_WINDOW_MS:
            break
        q.popleft()


async def binance_stream(symbols: list[str]) -> None:
    symbols = [normalize_binance_symbol(s) for s in symbols]
    trades: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=5000))
    context: dict[str, dict[str, Any]] = {}
    ctx_ts: dict[str, int] = defaultdict(int)
    last_write: dict[str, int] = defaultdict(int)
    rest = BinanceUSDm()

    while True:
        try:
            async with websockets.connect(settings.binance_ws, ping_interval=150, ping_timeout=30, max_queue=10000) as ws:
                params: list[str] = []
                for s in symbols:
                    params.extend([f"{s.lower()}@depth20@100ms", f"{s.lower()}@aggTrade"])
                await ws.send(json.dumps({"method": "SUBSCRIBE", "params": params, "id": 1}))
                async for raw in ws:
                    msg = json.loads(raw)
                    if "data" in msg and isinstance(msg["data"], dict):
                        msg = msg["data"]
                    typ = msg.get("e")
                    symbol = str(msg.get("s", "")).upper()
                    if symbol not in symbols:
                        continue
                    now = int(msg.get("E") or msg.get("T") or time.time() * 1000)
                    if typ == "aggTrade":
                        trades[symbol].append(msg)
                        _prune(trades[symbol], now)
                        continue
                    if "b" not in msg or "a" not in msg:
                        continue
                    if now - ctx_ts[symbol] >= CONTEXT_REFRESH_MS:
                        try:
                            context[symbol] = await rest.context(symbol)
                            ctx_ts[symbol] = now
                        except Exception:
                            pass
                    if now - last_write[symbol] < settings.snapshot_interval_ms:
                        continue
                    _prune(trades[symbol], now)
                    snap = merge_snapshot(
                        venue="binance",
                        symbol=symbol,
                        ts_ms=now,
                        bids=msg["b"],
                        asks=msg["a"],
                        trades=list(trades[symbol]),
                        context=context.get(symbol),
                    )
                    store.put_snapshot("binance", symbol, now, snap)
                    if snap.get("best_bid") and snap.get("best_ask"):
                        store.evaluate_shadow("binance", symbol, float(snap["best_bid"]), float(snap["best_ask"]), now)
                    last_write[symbol] = now
        except Exception as exc:
            print(f"binance stream reconnect: {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(2)


async def hyperliquid_stream(symbols: list[str]) -> None:
    coins = [normalize_hyperliquid_coin(s) for s in symbols]
    trades: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=5000))
    context: dict[str, dict[str, Any]] = {}
    last_write: dict[str, int] = defaultdict(int)

    while True:
        try:
            async with websockets.connect(settings.hyperliquid_ws, ping_interval=None, max_queue=10000) as ws:
                for coin in coins:
                    for sub in (
                        {"type": "l2Book", "coin": coin},
                        {"type": "trades", "coin": coin},
                        {"type": "activeAssetCtx", "coin": coin},
                    ):
                        await ws.send(json.dumps({"method": "subscribe", "subscription": sub}))

                async def heartbeat() -> None:
                    while True:
                        await asyncio.sleep(30)
                        await ws.send(json.dumps({"method": "ping"}))

                hb = asyncio.create_task(heartbeat())
                try:
                    async for raw in ws:
                        msg = json.loads(raw)
                        channel = msg.get("channel")
                        data = msg.get("data")
                        if channel == "trades" and isinstance(data, list):
                            for t in data:
                                coin = str(t.get("coin", "")).upper()
                                trades[coin].append(t)
                                _prune(trades[coin], int(t.get("time") or time.time()*1000))
                            continue
                        if channel == "activeAssetCtx" and isinstance(data, dict):
                            coin = str(data.get("coin", "")).upper()
                            ctx = data.get("ctx", {})
                            context[coin] = {
                                "mark_price": float(ctx["markPx"]) if ctx.get("markPx") else None,
                                "oracle_price": float(ctx["oraclePx"]) if ctx.get("oraclePx") else None,
                                "funding_rate": float(ctx["funding"]) if ctx.get("funding") not in (None, "") else None,
                                "open_interest": float(ctx["openInterest"]) if ctx.get("openInterest") not in (None, "") else None,
                                "day_notional_volume": float(ctx["dayNtlVlm"]) if ctx.get("dayNtlVlm") not in (None, "") else None,
                            }
                            continue
                        if channel != "l2Book" or not isinstance(data, dict):
                            continue
                        coin = str(data.get("coin", "")).upper()
                        if coin not in coins:
                            continue
                        now = int(data.get("time") or time.time() * 1000)
                        if now - last_write[coin] < settings.snapshot_interval_ms:
                            continue
                        _prune(trades[coin], now)
                        levels = data.get("levels") or [[], []]
                        snap = merge_snapshot(
                            venue="hyperliquid",
                            symbol=coin,
                            ts_ms=now,
                            bids=levels[0],
                            asks=levels[1],
                            trades=list(trades[coin]),
                            context=context.get(coin),
                        )
                        store.put_snapshot("hyperliquid", coin, now, snap)
                        if snap.get("best_bid") and snap.get("best_ask"):
                            store.evaluate_shadow("hyperliquid", coin, float(snap["best_bid"]), float(snap["best_ask"]), now)
                        last_write[coin] = now
                finally:
                    hb.cancel()
        except Exception as exc:
            print(f"hyperliquid stream reconnect: {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(2)


async def main() -> None:
    venues = {x.strip().lower() for x in os.getenv("STREAM_VENUES", "binance,hyperliquid").split(",") if x.strip()}
    tasks = []
    if "binance" in venues:
        tasks.append(asyncio.create_task(binance_stream(settings.stream_symbols)))
    if "hyperliquid" in venues:
        tasks.append(asyncio.create_task(hyperliquid_stream(settings.stream_symbols)))
    if not tasks:
        raise SystemExit("STREAM_VENUES is empty")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
