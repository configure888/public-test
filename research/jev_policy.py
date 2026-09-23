#!/usr/bin/env python3
"""Deterministic policy layer for a downstream Jev judgment.

Jev never gets authority over sizing, wallet access, stops, or execution. This
module only turns a calibrated typed judgment plus a Pine candidate into ACCEPT
or ABSTAIN. Probability thresholds are configuration, not model prose.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Policy:
    min_grouped_score: float = 78.0
    min_rr: float = 6.0
    min_direction_probability: float = 0.65
    min_setup_probability: float = 0.65
    require_a_plus: bool = True


def decide(candidate: dict[str, Any], judgment: dict[str, Any], policy: Policy = Policy()) -> dict[str, Any]:
    reasons=[]
    side=str(candidate.get("side",""))
    score=float(candidate.get("grouped_score",0) or 0)
    rr=float(candidate.get("rr",0) or 0)
    a_plus=bool(candidate.get("a_plus",False))
    direction=str(judgment.get("direction","unclear"))
    p_dir=float(judgment.get("direction_probability",0) or 0)
    p_setup=float(judgment.get("setup_probability",0) or 0)

    expected = "up" if side=="long" else "down" if side=="short" else "invalid"
    if expected=="invalid": reasons.append("invalid_side")
    if score < policy.min_grouped_score: reasons.append("internal_score")
    if rr < policy.min_rr: reasons.append("rr_gate")
    if policy.require_a_plus and not a_plus: reasons.append("not_a_plus")
    if direction != expected: reasons.append("jev_direction_disagrees")
    if p_dir < policy.min_direction_probability: reasons.append("jev_direction_uncertain")
    if p_setup < policy.min_setup_probability: reasons.append("jev_setup_uncertain")

    return {"action":"ABSTAIN" if reasons else "ACCEPT","reasons":reasons,"side":side,"score":score,"rr":rr,"direction":direction,"p_direction":p_dir,"p_setup":p_setup}
