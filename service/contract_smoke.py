#!/usr/bin/env python3
"""Public venue API contract smoke test.

No keys, accounts, or order endpoints are touched. Binance HTTP 451 is classified as
runner geofencing rather than a schema failure; Hyperliquid must still pass.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import websockets

from config import settings
from venues import BinanceUSDm, Hyperliquid


async def binance_rest() -> str:
    try:
        b = await BinanceUSDm(timeout=8).snapshot("BTCUSDT")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 451:
            print("binance_rest_geo_blocked_451")
            return "geo_blocked"
        raise
    assert b["venue"] == "binance"
    assert b["best_bid"] > 0 and b["best_ask"] > b["best_bid"]
    assert b["open_interest"] is not None
    assert b["mark_price"] is not None
    print("binance_rest_ok", {k:b.get(k) for k in ("symbol","spread_bps","funding_rate","open_interest")})
    return "ok"


async def binance_ws() -> str:
    try:
        async with websockets.connect(settings.binance_ws, open_timeout=8, close_timeout=2) as ws:
            await ws.send(json.dumps({"method":"SUBSCRIBE","params":["btcusdt@aggTrade"],"id":99}))
            for _ in range(20):
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                if msg.get("e") == "aggTrade" or (isinstance(msg.get("data"),dict) and msg["data"].get("e")=="aggTrade"):
                    print("binance_ws_ok")
                    return "ok"
            raise AssertionError("no Binance aggTrade received")
    except Exception as exc:
        text = str(exc)
        if "451" in text or "403" in text:
            print("binance_ws_geo_blocked", type(exc).__name__, text)
            return "geo_blocked"
        # A GitHub runner may be blocked at handshake without an HTTP body. If REST already
        # classified the environment as 451, the caller will handle this as non-schema failure.
        raise


async def hyperliquid_rest() -> None:
    h = await Hyperliquid(timeout=8).snapshot("BTCUSDT")
    assert h["venue"] == "hyperliquid"
    assert h["best_bid"] > 0 and h["best_ask"] > h["best_bid"]
    assert h["open_interest"] is not None
    assert h["mark_price"] is not None
    print("hyperliquid_rest_ok", {k:h.get(k) for k in ("symbol","spread_bps","funding_rate","open_interest")})


async def hyperliquid_ws() -> None:
    async with websockets.connect(settings.hyperliquid_ws, open_timeout=8, close_timeout=2, ping_interval=None) as ws:
        await ws.send(json.dumps({"method":"subscribe","subscription":{"type":"l2Book","coin":"BTC"}}))
        for _ in range(20):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
            if msg.get("channel") == "l2Book":
                data = msg.get("data") or {}
                levels = data.get("levels") or [[],[]]
                assert levels[0] and levels[1]
                print("hyperliquid_ws_ok")
                return
        raise AssertionError("no Hyperliquid l2Book received")


async def main() -> None:
    b_rest = await binance_rest()
    if b_rest == "ok":
        await binance_ws()
    else:
        print("binance_ws_skipped_due_to_runner_geofence")
    await hyperliquid_rest()
    await hyperliquid_ws()


if __name__ == "__main__":
    asyncio.run(main())
