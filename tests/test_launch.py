import json
import os
import tempfile
import unittest

from peer.launch import run


class TestLaunch(unittest.TestCase):
    def test_every_peer_writes_a_log(self):
        log_dir = tempfile.mkdtemp()
        config = {"bots": 3, "benign": 7, "duration": 1, "log_dir": log_dir,
                  "base_port": 9201, "random_seed": 1, "join_gap": 0.02,
                  "all": {"max_peers": 3, "exchange_interval": 0.3},
                  "rendezvous_peers": 2, "ultrapeer_fraction": 0.3,
                  "bot_settings": {"rendezvous_preference": 0.8}}
        run(config)

        logs = [f for f in os.listdir(log_dir) if f.endswith(".jsonl")]
        self.assertEqual(len(logs), 10)
        roles = []
        for name in logs:
            with open(os.path.join(log_dir, name)) as f:
                lines = [json.loads(line) for line in f]
            if lines:
                roles.append(lines[0]["role"])
        self.assertEqual(roles.count("bot"), 3)
        with open(os.path.join(log_dir, "config.json")) as f:
            saved = json.load(f)
        self.assertEqual(len(saved["rendezvous_ports"]), 2)
        self.assertEqual(len(saved["ultrapeer_ports"]), 2)  # 30% of 7 benign, rounded
        self.assertFalse(set(saved["rendezvous_ports"]) & set(saved["ultrapeer_ports"]))


if __name__ == "__main__":
    unittest.main()