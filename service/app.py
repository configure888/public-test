from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import settings
from storage import Store
from jev_request import build_request
from venues import (
    choose_venue,
    live_snapshot,
    normalize_binance_symbol,
    normalize_hyperliquid_coin,
)

app = FastAPI(title="Pattern Intelligence Research Gateway", version="0.1.0")
store = Store(settings.db_path)


class JevDecision(BaseModel):
    event_id: str
    action: str = Field(pattern="^(ACCEPT|ABSTAIN)$")
    direction: str | None = None
    direction_probability: float | None = Field(default=None, ge=0, le=1)
    setup_probability: float | None = Field(default=None, ge=0, le=1)
    liquidity_safe: bool | None = None
    toxic_flow: bool | None = None
    execution_environment: str | None = None
    reason: str | None = None


def _normalized_symbol(raw: str, venue: str) -> str:
    return normalize_hyperliquid_coin(raw) if venue == "hyperliquid" else normalize_binance_symbol(raw)


def _passes_shadow_gate(payload: dict[str, Any]) -> bool:
    try:
        score = float(payload.get("grouped_score", payload.get("score", payload.get("legacy_score", 0))) or 0)
        rr = float(payload.get("rr", 0) or 0)
    except (TypeError, ValueError):
        return False
    return bool(payload.get("a_plus", False)) and score >= settings.shadow_min_score and rr >= settings.shadow_min_rr


def _jev_passes(side: str, decision: JevDecision) -> bool:
    expected = "up" if side == "long" else "down" if side == "short" else "invalid"
    return (
        decision.action == "ACCEPT"
        and decision.direction == expected
        and decision.direction_probability is not None
        and decision.direction_probability >= settings.jev_min_direction_probability
        and decision.setup_probability is not None
        and decision.setup_probability >= settings.jev_min_setup_probability
        and decision.liquidity_safe is True
        and decision.toxic_flow is False
        and decision.execution_environment in {"favorable", "marginal"}
    )


async def _enrich(event_id: str, payload: dict[str, Any]) -> None:
    raw_symbol = str(payload.get("symbol", ""))
    venue = choose_venue(raw_symbol, settings.primary_venue)
    symbol = _normalized_symbol(raw_symbol, venue)
    event_ts = int(payload.get("time") or int(time.time() * 1000))

    snap = store.nearest_snapshot(venue, symbol, event_ts, settings.snapshot_max_age_ms)
    source = "stream_cache"
    if snap is None:
        source = "rest_live"
        try:
            snap = await asyncio.wait_for(live_snapshot(raw_symbol, venue), timeout=settings.enrich_timeout_s + 0.5)
            store.put_snapshot(venue, symbol, int(snap["ts_ms"]), snap)
        except Exception as exc:
            store.attach_enrichment(event_id, {"venue": venue, "symbol": symbol, "error": type(exc).__name__, "message": str(exc)}, status="ENRICH_FAILED")
            return

    snap = dict(snap)
    snap["enrichment_source"] = source
    snap["event_ts_ms"] = event_ts
    snap["capture_distance_ms"] = abs(int(snap.get("ts_ms", event_ts)) - event_ts)
    snap["stale"] = snap["capture_distance_ms"] > settings.snapshot_max_age_ms
    store.attach_enrichment(event_id, snap)

    if settings.shadow_auto_arm and not settings.shadow_require_jev and _passes_shadow_gate(payload):
        store.arm_shadow(event_id, venue, {**payload, "symbol": symbol}, source="pine")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": app.version, **store.health_counts()}


@app.post("/webhook/tradingview/{token}")
async def tradingview(token: str, payload: dict[str, Any], background: BackgroundTasks) -> dict[str, Any]:
    if token != settings.webhook_token:
        raise HTTPException(404, "not found")
    if payload.get("type") not in {"research_candidate", "jev_candidate"}:
        raise HTTPException(422, "unsupported payload type")
    created, event_id = store.insert_event(payload)
    if created:
        background.add_task(_enrich, event_id, payload)
    return {"ok": True, "created": created, "event_id": event_id}


@app.post("/webhook/jev/{token}")
def jev(token: str, decision: JevDecision) -> dict[str, Any]:
    if token != settings.jev_token:
        raise HTTPException(404, "not found")
    event = store.get_event(decision.event_id)
    if event is None:
        raise HTTPException(404, "event not found")
    data = decision.model_dump()
    store.record_jev(decision.event_id, data)

    armed = False
    payload = event["payload"]
    if _jev_passes(str(payload.get("side", "")).lower(), decision):
        if _passes_shadow_gate(payload):
            raw_symbol = str(payload.get("symbol", ""))
            venue = choose_venue(raw_symbol, settings.primary_venue)
            symbol = _normalized_symbol(raw_symbol, venue)
            armed = store.arm_shadow(decision.event_id, venue, {**payload, "symbol": symbol}, source="jev")
    return {"ok": True, "armed_shadow": armed}


@app.get("/events/{event_id}")
def event(event_id: str) -> dict[str, Any]:
    out = store.get_event(event_id)
    if out is None:
        raise HTTPException(404, "event not found")
    return out


@app.get("/jev/request/{event_id}")
def jev_request(event_id: str) -> dict[str, Any]:
    out = store.get_event(event_id)
    if out is None:
        raise HTTPException(404, "event not found")
    if out.get("enrichment") is None:
        raise HTTPException(409, "event not enriched yet")
    return build_request(out)
