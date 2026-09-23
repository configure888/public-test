from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _levels(raw: Iterable[Any]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for level in raw:
        if isinstance(level, dict):
            px, qty = level.get("px"), level.get("sz")
        else:
            px, qty = level[0], level[1]
        out.append((float(px), float(qty)))
    return out


def book_features(bids_raw: Iterable[Any], asks_raw: Iterable[Any]) -> dict[str, float | None]:
    bids = sorted(_levels(bids_raw), key=lambda x: x[0], reverse=True)
    asks = sorted(_levels(asks_raw), key=lambda x: x[0])
    if not bids or not asks:
        return {"mid": None, "spread_bps": None, "microprice": None}

    bid, bid_q = bids[0]
    ask, ask_q = asks[0]
    mid = (bid + ask) / 2.0
    spread = ask - bid
    denom = bid_q + ask_q
    micro = ((ask * bid_q) + (bid * ask_q)) / denom if denom > 0 else mid

    out: dict[str, float | None] = {
        "best_bid": bid,
        "best_ask": ask,
        "best_bid_qty": bid_q,
        "best_ask_qty": ask_q,
        "mid": mid,
        "spread": spread,
        "spread_bps": spread / mid * 10_000 if mid else None,
        "microprice": micro,
        "microprice_edge_bps": (micro - mid) / mid * 10_000 if mid else None,
    }
    for n in (5, 10, 20):
        bd = sum(q for _, q in bids[:n])
        ad = sum(q for _, q in asks[:n])
        total = bd + ad
        out[f"bid_depth_{n}"] = bd
        out[f"ask_depth_{n}"] = ad
        out[f"book_imbalance_{n}"] = (bd - ad) / total if total else 0.0
    return out


def trade_features(trades: Iterable[dict[str, Any]], venue: str) -> dict[str, float | int | None]:
    buy = sell = buy_notional = sell_notional = 0.0
    count = 0
    first_ts: int | None = None
    last_ts: int | None = None
    for t in trades:
        count += 1
        px = float(t.get("p", t.get("px", 0.0)))
        qty = float(t.get("q", t.get("sz", 0.0)))
        ts = int(t.get("T", t.get("time", t.get("E", 0))) or 0)
        first_ts = ts if first_ts is None else min(first_ts, ts)
        last_ts = ts if last_ts is None else max(last_ts, ts)
        if venue == "binance":
            # m=True => buyer is maker, therefore the aggressor was a seller.
            is_buy = not bool(t.get("m", False))
        else:
            # Hyperliquid WsTrade: side B means buyer aggressed, A means seller aggressed.
            is_buy = str(t.get("side", "")).upper() == "B"
        if is_buy:
            buy += qty
            buy_notional += qty * px
        else:
            sell += qty
            sell_notional += qty * px

    total = buy + sell
    total_notional = buy_notional + sell_notional
    return {
        "trade_count": count,
        "taker_buy_qty": buy,
        "taker_sell_qty": sell,
        "trade_imbalance": (buy - sell) / total if total else 0.0,
        "cvd_qty": buy - sell,
        "taker_buy_notional": buy_notional,
        "taker_sell_notional": sell_notional,
        "cvd_notional": buy_notional - sell_notional,
        "buy_notional_ratio": buy_notional / total_notional if total_notional else None,
        "trade_window_ms": (last_ts - first_ts) if first_ts is not None and last_ts is not None else None,
    }


def merge_snapshot(
    *,
    venue: str,
    symbol: str,
    ts_ms: int,
    bids: Iterable[Any],
    asks: Iterable[Any],
    trades: Iterable[dict[str, Any]] = (),
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"venue": venue, "symbol": symbol, "ts_ms": int(ts_ms)}
    out.update(book_features(bids, asks))
    out.update(trade_features(trades, venue))
    if context:
        out.update(context)
    mark = out.get("mark_price")
    index = out.get("index_price", out.get("oracle_price"))
    if mark is not None and index not in (None, 0, 0.0):
        out["basis_bps"] = (float(mark) - float(index)) / float(index) * 10_000
    return out
