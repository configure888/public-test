#!/usr/bin/env python3
"""Public venue API contract smoke test.

No keys, accounts, or order endpoints are touched.
"""
from __future__ import annotations

import asyncio

from venues import BinanceUSDm, Hyperliquid


async def main() -> None:
    b = await BinanceUSDm(timeout=8).snapshot("BTCUSDT")
    assert b["venue"] == "binance"
    assert b["best_bid"] > 0 and b["best_ask"] > b["best_bid"]
    assert b["open_interest"] is not None
    assert b["mark_price"] is not None
    print("binance_ok", {k:b.get(k) for k in ("symbol","spread_bps","funding_rate","open_interest")})

    h = await Hyperliquid(timeout=8).snapshot("BTCUSDT")
    assert h["venue"] == "hyperliquid"
    assert h["best_bid"] > 0 and h["best_ask"] > h["best_bid"]
    assert h["open_interest"] is not None
    assert h["mark_price"] is not None
    print("hyperliquid_ok", {k:h.get(k) for k in ("symbol","spread_bps","funding_rate","open_interest")})


if __name__ == "__main__":
    asyncio.run(main())
