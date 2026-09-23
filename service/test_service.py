from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from features import book_features, trade_features
from jev_request import build_request
from storage import Store
from venues import normalize_binance_symbol, normalize_hyperliquid_coin


class FeaturesTest(unittest.TestCase):
    def test_book_features(self):
        x = book_features([["100", "3"], ["99", "2"]], [["101", "1"], ["102", "2"]])
        self.assertEqual(x["best_bid"], 100.0)
        self.assertEqual(x["best_ask"], 101.0)
        self.assertGreater(x["book_imbalance_5"], 0)
        self.assertGreater(x["microprice"], x["mid"])

    def test_binance_aggressor_side(self):
        trades = [
            {"p":"100","q":"2","T":1000,"m":False},  # buyer taker
            {"p":"101","q":"1","T":1100,"m":True},   # seller taker
        ]
        x = trade_features(trades, "binance")
        self.assertEqual(x["taker_buy_qty"], 2.0)
        self.assertEqual(x["taker_sell_qty"], 1.0)
        self.assertGreater(x["trade_imbalance"], 0)

    def test_symbols(self):
        self.assertEqual(normalize_binance_symbol("BINANCE:BTCUSDT.P"), "BTCUSDT")
        self.assertEqual(normalize_hyperliquid_coin("HYPERLIQUID:BTCUSDC"), "BTC")


class StoreTest(unittest.TestCase):
    def test_idempotency_enrichment_and_shadow(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(str(Path(td) / "db.sqlite"))
            p = {
                "type":"research_candidate","event_id":"e1","symbol":"BINANCE:BTCUSDT",
                "tf":"5","time":1000,"side":"long","family":"reversal",
                "entry":100.0,"stop":99.0,"target":106.0,"rr":6.0,
                "grouped_score":85.0,"a_plus":True,
            }
            self.assertTrue(store.insert_event(p)[0])
            self.assertFalse(store.insert_event(p)[0])
            store.attach_enrichment("e1", {"spread_bps":1.2})
            self.assertEqual(store.get_event("e1")["enrichment"]["spread_bps"], 1.2)
            self.assertTrue(store.arm_shadow("e1","binance",{**p,"symbol":"BTCUSDT"},"test"))
            self.assertFalse(store.arm_shadow("e1","binance",{**p,"symbol":"BTCUSDT"},"test"))
            self.assertEqual(store.evaluate_shadow("binance","BTCUSDT",106.1,106.2,2000)[0]["status"], "TARGET")

    def test_shadow_stop(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(str(Path(td) / "db.sqlite"))
            p = {"type":"research_candidate","event_id":"e2","symbol":"BTCUSDT","tf":"5","side":"short","entry":100.0,"stop":101.0,"target":94.0,"rr":6.0}
            store.insert_event(p)
            store.arm_shadow("e2","binance",p,"test")
            closed = store.evaluate_shadow("binance","BTCUSDT",101.0,101.1,2000)
            self.assertEqual(closed[0]["realized_r"], -1.0)

    def test_jev_request_is_atomic(self):
        req = build_request({
            "event_id":"e1",
            "payload":{"symbol":"BTCUSDT","tf":"5","side":"long","family":"reversal","grouped_score":82,"rr":6.5},
            "enrichment":{"spread_bps":1.0,"book_imbalance_5":0.2},
        })
        self.assertEqual(req["candidate"]["event_id"], "e1")
        self.assertIn("direction_probability", req["output_schema"])
        self.assertNotIn("size", req["candidate"])


if __name__ == "__main__":
    unittest.main()
