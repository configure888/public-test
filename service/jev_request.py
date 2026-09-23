from __future__ import annotations

from typing import Any


OUTPUT_SCHEMA = {
    "direction": "up|down|unclear",
    "direction_probability": "number 0..1",
    "follow_through": "continuation|reversal|no-pattern",
    "setup_quality": "low|medium|high|exceptional",
    "setup_probability": "number 0..1",
    "liquidity_safe": "boolean",
    "toxic_flow": "boolean",
    "execution_environment": "favorable|marginal|avoid",
    "reason_codes": ["short_machine_readable_codes"],
}


def build_request(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    micro = event.get("enrichment") or {}
    return {
        "task": "Atomic pre-trade adjudication. Abstain when evidence is insufficient. Do not size or place orders.",
        "candidate": {
            "event_id": event.get("event_id"),
            "symbol": payload.get("symbol"),
            "timeframe": payload.get("tf"),
            "side": payload.get("side"),
            "family": payload.get("family"),
            "grouped_score": payload.get("grouped_score", payload.get("score")),
            "projected_rr": payload.get("rr"),
            "entry": payload.get("entry"),
            "stop": payload.get("stop"),
            "target": payload.get("target", payload.get("dol")),
            "mtf_votes": payload.get("mtf_votes"),
            "sweep": payload.get("sweep"),
            "smt": payload.get("smt"),
            "regular_divergence": payload.get("regular_div"),
            "hidden_divergence": payload.get("hidden_div"),
            "fvg": payload.get("fvg"),
            "ifvg": payload.get("ifvg"),
            "order_block": payload.get("ob"),
            "ote": payload.get("ote"),
            "coil": payload.get("coil"),
            "vwap_z": payload.get("vwap_z"),
        },
        "microstructure": {
            k: micro.get(k) for k in (
                "spread_bps","microprice_edge_bps","book_imbalance_5","book_imbalance_10","book_imbalance_20",
                "trade_imbalance","cvd_notional","buy_notional_ratio","funding_rate","open_interest","basis_bps",
                "capture_distance_ms","stale",
            )
        },
        "output_schema": OUTPUT_SCHEMA,
    }
