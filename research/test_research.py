import unittest

from label_candidates import Bar, label_one
from validate import summary
from jev_policy import decide


class ResearchToolsTest(unittest.TestCase):
    def test_long_six_r_before_stop(self):
        ev = {"type": "research_candidate", "time": 1000, "side": "long", "entry": 100.0, "stop": 99.0, "target": 106.0}
        bars = [
            Bar(1000, 100.0, 101.0, 99.5, 100.5),
            Bar(2000, 100.5, 103.0, 100.0, 102.5),
            Bar(3000, 102.5, 106.2, 102.0, 106.0),
        ]
        out = label_one(ev, bars, 10, [1.0, 2.0, 3.0, 4.0, 6.0])
        self.assertTrue(out["six_r_before_stop"])
        self.assertEqual(out["contract_r"], 6.0)
        self.assertIsNone(out["stop_bar"])

    def test_same_bar_stop_wins(self):
        ev = {"type":"research_candidate","time":1000,"side":"long","entry":100.0,"stop":99.0,"target":106.0}
        bars = [Bar(1000, 100.0, 106.5, 98.5, 100.0)]
        out = label_one(ev, bars, 10, [6.0])
        self.assertFalse(out["six_r_before_stop"])
        self.assertEqual(out["contract_r"], -1.0)

    def test_wilson_and_summary(self):
        rows = [{"six_r_before_stop": i < 8, "contract_r": 6.0 if i < 8 else -1.0, "mfe_r": 6.0, "mae_r": 0.5} for i in range(10)]
        s = summary(rows)
        self.assertEqual(s["n"], 10)
        self.assertAlmostEqual(s["win_rate_6r"], 0.8)
        self.assertGreater(s["wilson95_high"], s["wilson95_low"])
        self.assertAlmostEqual(s["expectancy_r"], 4.6)

    def test_jev_is_only_a_gate(self):
        candidate = {"side":"long","grouped_score":85,"rr":7,"a_plus":True}
        judgment = {"direction":"up","direction_probability":0.8,"setup_probability":0.75}
        self.assertEqual(decide(candidate, judgment)["action"], "ACCEPT")
        judgment["direction_probability"] = 0.5
        self.assertEqual(decide(candidate, judgment)["action"], "ABSTAIN")


if __name__ == "__main__":
    unittest.main()
