import csv
import os
import tempfile
import unittest

from experiments.sweep import sweep


class TestSweep(unittest.TestCase):
    def test_runs_every_combination_once(self):
        folder = tempfile.mkdtemp()
        plan = {"bots": 3, "benign_per_bot": [2], "rendezvous_preference": [0.0, 1.0],
                "repeats": 1, "duration": 1, "rendezvous_peers": 2, "base_port": 9301,
                "log_root": os.path.join(folder, "logs"),
                "results": os.path.join(folder, "results.csv"), "pause": 0.5,
                "all": {"max_peers": 3, "ping_interval": 0.2, "exchange_interval": 0.3}}
        sweep(plan)
        sweep(plan)  # second time finds both runs done and skips them

        with open(plan["results"]) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(sorted(r["run"] for r in rows), ["b2_s0.0_r1", "b2_s1.0_r1"])


if __name__ == "__main__":
    unittest.main()