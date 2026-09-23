from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("DB_PATH", "/data/trading.db")
    webhook_token: str = os.getenv("TV_WEBHOOK_TOKEN", "change-me")
    jev_token: str = os.getenv("JEV_WEBHOOK_TOKEN", "change-me-too")
    primary_venue: str = os.getenv("PRIMARY_VENUE", "auto").lower()
    enrich_timeout_s: float = float(os.getenv("ENRICH_TIMEOUT_S", "3.0"))
    snapshot_max_age_ms: int = int(os.getenv("SNAPSHOT_MAX_AGE_MS", "5000"))
    snapshot_interval_ms: int = int(os.getenv("SNAPSHOT_INTERVAL_MS", "1000"))
    stream_symbols: list[str] = None  # type: ignore[assignment]
    binance_rest: str = os.getenv("BINANCE_REST", "https://fapi.binance.com")
    binance_ws: str = os.getenv("BINANCE_WS", "wss://fstream.binance.com/public/ws")
    hyperliquid_info: str = os.getenv("HYPERLIQUID_INFO", "https://api.hyperliquid.xyz/info")
    hyperliquid_ws: str = os.getenv("HYPERLIQUID_WS", "wss://api.hyperliquid.xyz/ws")
    shadow_auto_arm: bool = _bool("SHADOW_AUTO_ARM", False)
    shadow_require_jev: bool = _bool("SHADOW_REQUIRE_JEV", True)
    shadow_min_score: float = float(os.getenv("SHADOW_MIN_SCORE", "78"))
    shadow_min_rr: float = float(os.getenv("SHADOW_MIN_RR", "6"))
    jev_min_direction_probability: float = float(os.getenv("JEV_MIN_DIRECTION_PROBABILITY", "0.65"))
    jev_min_setup_probability: float = float(os.getenv("JEV_MIN_SETUP_PROBABILITY", "0.65"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "stream_symbols", _list("STREAM_SYMBOLS", "BTCUSDT,ETHUSDT"))

settings = Settings()
