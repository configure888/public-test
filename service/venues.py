from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from config import settings
from features import merge_snapshot


def normalize_binance_symbol(raw: str) -> str:
    s = raw.split(":")[-1].upper().replace("/", "").replace("-", "")
    if s.endswith(".P"):
        s = s[:-2]
    return s


def normalize_hyperliquid_coin(raw: str) -> str:
    s = raw.split(":")[-1].upper().replace("/", "").replace("-", "")
    if s.endswith(".P"):
        s = s[:-2]
    for suffix in ("USDT", "USDC", "USD"):
        if s.endswith(suffix) and len(s) > len(suffix):
            s = s[: -len(suffix)]
            break
    return s


def choose_venue(raw_symbol: str, configured: str = "auto") -> str:
    if configured in {"binance", "hyperliquid"}:
        return configured
    upper = raw_symbol.upper()
    if upper.startswith("HYPERLIQUID:") or upper.startswith("HL:"):
        return "hyperliquid"
    return "binance"


class BinanceUSDm:
    venue = "binance"

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base = (base_url or settings.binance_rest).rstrip("/")
        self.timeout = timeout or settings.enrich_timeout_s

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(base_url=self.base, timeout=self.timeout) as client:
            r = await client.get(path, params=params)
            r.raise_for_status()
            return r.json()

    async def context(self, symbol: str) -> dict[str, Any]:
        premium, oi = await asyncio.gather(
            self._get("/fapi/v1/premiumIndex", {"symbol": symbol}),
            self._get("/fapi/v1/openInterest", {"symbol": symbol}),
        )
        return {
            "mark_price": float(premium["markPrice"]) if premium.get("markPrice") else None,
            "index_price": float(premium["indexPrice"]) if premium.get("indexPrice") else None,
            "funding_rate": float(premium["lastFundingRate"]) if premium.get("lastFundingRate") not in (None, "") else None,
            "next_funding_time": int(premium["nextFundingTime"]) if premium.get("nextFundingTime") else None,
            "open_interest": float(oi["openInterest"]) if oi.get("openInterest") else None,
            "context_ts_ms": int(premium.get("time") or oi.get("time") or time.time() * 1000),
        }

    async def snapshot(self, raw_symbol: str) -> dict[str, Any]:
        symbol = normalize_binance_symbol(raw_symbol)
        depth, trades, context = await asyncio.gather(
            self._get("/fapi/v1/depth", {"symbol": symbol, "limit": 20}),
            self._get("/fapi/v1/aggTrades", {"symbol": symbol, "limit": 500}),
            self.context(symbol),
        )
        ts = int(depth.get("T") or depth.get("E") or time.time() * 1000)
        return merge_snapshot(
            venue=self.venue,
            symbol=symbol,
            ts_ms=ts,
            bids=depth.get("bids", []),
            asks=depth.get("asks", []),
            trades=trades,
            context=context,
        )


class Hyperliquid:
    venue = "hyperliquid"

    def __init__(self, info_url: str | None = None, timeout: float | None = None):
        self.url = info_url or settings.hyperliquid_info
        self.timeout = timeout or settings.enrich_timeout_s

    async def _post(self, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(self.url, json=payload)
            r.raise_for_status()
            return r.json()

    async def context(self, coin: str) -> dict[str, Any]:
        response = await self._post({"type": "metaAndAssetCtxs"})
        meta, ctxs = response
        universe = meta.get("universe", [])
        for item, ctx in zip(universe, ctxs):
            if str(item.get("name", "")).upper() == coin.upper():
                return {
                    "mark_price": float(ctx["markPx"]) if ctx.get("markPx") else None,
                    "oracle_price": float(ctx["oraclePx"]) if ctx.get("oraclePx") else None,
                    "funding_rate": float(ctx["funding"]) if ctx.get("funding") not in (None, "") else None,
                    "open_interest": float(ctx["openInterest"]) if ctx.get("openInterest") not in (None, "") else None,
                    "day_notional_volume": float(ctx["dayNtlVlm"]) if ctx.get("dayNtlVlm") not in (None, "") else None,
                    "premium": float(ctx["premium"]) if ctx.get("premium") not in (None, "") else None,
                    "context_ts_ms": int(time.time() * 1000),
                }
        raise ValueError(f"Hyperliquid coin not found: {coin}")

    async def snapshot(self, raw_symbol: str) -> dict[str, Any]:
        coin = normalize_hyperliquid_coin(raw_symbol)
        book, context = await asyncio.gather(
            self._post({"type": "l2Book", "coin": coin}),
            self.context(coin),
        )
        levels = book.get("levels") or [[], []]
        return merge_snapshot(
            venue=self.venue,
            symbol=coin,
            ts_ms=int(book.get("time") or time.time() * 1000),
            bids=levels[0],
            asks=levels[1],
            trades=(),
            context=context,
        )


async def live_snapshot(raw_symbol: str, venue: str | None = None) -> dict[str, Any]:
    selected = choose_venue(raw_symbol, venue or settings.primary_venue)
    if selected == "hyperliquid":
        return await Hyperliquid().snapshot(raw_symbol)
    return await BinanceUSDm().snapshot(raw_symbol)
