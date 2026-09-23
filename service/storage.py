from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    received_ms INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    side TEXT,
    family TEXT,
    payload_json TEXT NOT NULL,
    enrichment_json TEXT,
    enrichment_ts_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'RECEIVED'
);
CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_ms);
CREATE INDEX IF NOT EXISTS idx_events_symbol ON events(symbol, received_ms);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    symbol TEXT NOT NULL,
    ts_ms INTEGER NOT NULL,
    features_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON snapshots(venue, symbol, ts_ms);

CREATE TABLE IF NOT EXISTS jev_decisions (
    event_id TEXT PRIMARY KEY,
    received_ms INTEGER NOT NULL,
    action TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(event_id)
);

CREATE TABLE IF NOT EXISTS shadow_trades (
    event_id TEXT PRIMARY KEY,
    venue TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry REAL NOT NULL,
    stop REAL NOT NULL,
    target REAL NOT NULL,
    projected_rr REAL,
    opened_ms INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    closed_ms INTEGER,
    exit_px REAL,
    realized_r REAL,
    source TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(event_id)
);
CREATE INDEX IF NOT EXISTS idx_shadow_open ON shadow_trades(status, venue, symbol);
"""


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._puts = 0
        self._snapshot_max_rows = int(os.getenv("SNAPSHOT_RETENTION_ROWS", "500000"))
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def insert_event(self, payload: dict[str, Any]) -> tuple[bool, str]:
        event_id = str(payload.get("event_id") or f"{payload.get('symbol','NA')}-{payload.get('tf','NA')}-{payload.get('side','NA')}-{payload.get('time', int(time.time()*1000))}")
        now = int(time.time() * 1000)
        with self._lock, self._connect() as db:
            cur = db.execute(
                """INSERT OR IGNORE INTO events
                (event_id,received_ms,event_type,symbol,timeframe,side,family,payload_json,status)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    now,
                    str(payload.get("type", "unknown")),
                    str(payload.get("symbol", "")),
                    str(payload.get("tf", "")),
                    str(payload.get("side", "")),
                    str(payload.get("family", "")),
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    "RECEIVED",
                ),
            )
            return cur.rowcount == 1, event_id

    def attach_enrichment(self, event_id: str, features: dict[str, Any], status: str = "ENRICHED") -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE events SET enrichment_json=?, enrichment_ts_ms=?, status=? WHERE event_id=?",
                (json.dumps(features, separators=(",", ":"), sort_keys=True), int(time.time()*1000), status, event_id),
            )

    def put_snapshot(self, venue: str, symbol: str, ts_ms: int, features: dict[str, Any]) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO snapshots(venue,symbol,ts_ms,features_json) VALUES(?,?,?,?)",
                (venue, symbol, int(ts_ms), json.dumps(features, separators=(",", ":"), sort_keys=True)),
            )
            self._puts += 1
            # Prune in batches instead of issuing an expensive retention DELETE on every market tick.
            if self._snapshot_max_rows > 0 and self._puts % 1000 == 0:
                db.execute(
                    "DELETE FROM snapshots WHERE id IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT -1 OFFSET ?)",
                    (self._snapshot_max_rows,),
                )

    def nearest_snapshot(self, venue: str, symbol: str, ts_ms: int, max_age_ms: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT ts_ms,features_json FROM snapshots
                   WHERE venue=? AND symbol=? AND ts_ms BETWEEN ? AND ?
                   ORDER BY ABS(ts_ms-?) LIMIT 1""",
                (venue, symbol, ts_ms-max_age_ms, ts_ms+max_age_ms, ts_ms),
            ).fetchone()
        if not row:
            return None
        out = json.loads(row["features_json"])
        out["snapshot_distance_ms"] = abs(int(row["ts_ms"]) - int(ts_ms))
        return out

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        d["enrichment"] = json.loads(d.pop("enrichment_json")) if d.get("enrichment_json") else None
        return d

    def record_jev(self, event_id: str, payload: dict[str, Any]) -> None:
        action = str(payload.get("action", "ABSTAIN")).upper()
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO jev_decisions(event_id,received_ms,action,payload_json) VALUES(?,?,?,?)",
                (event_id, int(time.time()*1000), action, json.dumps(payload, separators=(",", ":"), sort_keys=True)),
            )

    def arm_shadow(self, event_id: str, venue: str, payload: dict[str, Any], source: str) -> bool:
        try:
            entry, stop, target = map(float, (payload["entry"], payload["stop"], payload.get("target", payload.get("dol"))))
        except (KeyError, TypeError, ValueError):
            return False
        rr = payload.get("rr")
        with self._lock, self._connect() as db:
            cur = db.execute(
                """INSERT OR IGNORE INTO shadow_trades
                (event_id,venue,symbol,side,entry,stop,target,projected_rr,opened_ms,status,source)
                VALUES(?,?,?,?,?,?,?,?,?,'OPEN',?)""",
                (event_id, venue, str(payload["symbol"]), str(payload["side"]).lower(), entry, stop, target, float(rr) if rr is not None else None, int(time.time()*1000), source),
            )
            return cur.rowcount == 1

    def evaluate_shadow(self, venue: str, symbol: str, bid: float, ask: float, ts_ms: int) -> list[dict[str, Any]]:
        closed: list[dict[str, Any]] = []
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM shadow_trades WHERE status='OPEN' AND venue=? AND symbol=?",
                (venue, symbol),
            ).fetchall()
            for row in rows:
                side = row["side"]
                stop_hit = bid <= row["stop"] if side == "long" else ask >= row["stop"]
                target_hit = bid >= row["target"] if side == "long" else ask <= row["target"]
                # In the unlikely case both become true in one sampled state, loss wins.
                if not stop_hit and not target_hit:
                    continue
                exit_px = row["stop"] if stop_hit else row["target"]
                risk = (row["entry"] - row["stop"]) if side == "long" else (row["stop"] - row["entry"])
                realized = -1.0 if stop_hit else (((row["target"] - row["entry"]) / risk) if side == "long" else ((row["entry"] - row["target"]) / risk))
                db.execute(
                    "UPDATE shadow_trades SET status=?,closed_ms=?,exit_px=?,realized_r=? WHERE event_id=?",
                    ("STOPPED" if stop_hit else "TARGET", int(ts_ms), float(exit_px), float(realized), row["event_id"]),
                )
                closed.append({"event_id": row["event_id"], "status": "STOPPED" if stop_hit else "TARGET", "realized_r": realized})
        return closed

    def health_counts(self) -> dict[str, int]:
        with self._connect() as db:
            return {
                "events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "snapshots": db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],
                "shadow_open": db.execute("SELECT COUNT(*) FROM shadow_trades WHERE status='OPEN'").fetchone()[0],
                "shadow_closed": db.execute("SELECT COUNT(*) FROM shadow_trades WHERE status!='OPEN'").fetchone()[0],
            }

    def latest_snapshots(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT s.venue,s.symbol,s.ts_ms
                   FROM snapshots s
                   JOIN (
                     SELECT venue,symbol,MAX(ts_ms) AS max_ts
                     FROM snapshots GROUP BY venue,symbol
                   ) x ON x.venue=s.venue AND x.symbol=s.symbol AND x.max_ts=s.ts_ms
                   ORDER BY s.venue,s.symbol"""
            ).fetchall()
        now = int(time.time()*1000)
        return [{"venue":r["venue"],"symbol":r["symbol"],"ts_ms":r["ts_ms"],"age_ms":now-int(r["ts_ms"])} for r in rows]
