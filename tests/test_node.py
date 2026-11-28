import json
import os
import tempfile
import time
import unittest

from peer.node import Peer


def read_log(log_dir, port):
    with open(os.path.join(log_dir, f"{port}.jsonl")) as f:
        return [json.loads(line) for line in f]


class TestPeers(unittest.TestCase):
    def setUp(self):
        self.log_dir = tempfile.mkdtemp()

    def test_hello_ping_pong(self):
        a = Peer(9101, ping_interval=0.1, log_dir=self.log_dir)
        b = Peer(9102, role="bot", ping_interval=0.1, log_dir=self.log_dir)
        a.start()
        b.start()
        b.connect(9101)
        time.sleep(0.5)
        a.stop()
        b.stop()

        a_events = [(e["event"], e["peer"]) for e in read_log(self.log_dir, 9101)]
        b_events = [(e["event"], e["peer"]) for e in read_log(self.log_dir, 9102)]
        self.assertIn(("hello", 9102), a_events)
        self.assertIn(("ping", 9102), a_events)
        self.assertIn(("hello", 9101), b_events)
        self.assertIn(("pong", 9101), b_events)

    def test_log_lines_have_all_fields(self):
        a = Peer(9111, log_dir=self.log_dir)
        b = Peer(9112, role="bot", log_dir=self.log_dir)
        a.start()
        b.start()
        b.connect(9111)
        time.sleep(0.3)
        a.stop()
        b.stop()

        for entry in read_log(self.log_dir, 9112):
            self.assertEqual(set(entry), {"ts", "node", "event", "peer", "bytes", "role"})
            self.assertEqual(entry["role"], "bot")

    def test_peers_found_through_seed(self):
        # One seed, five newcomers that only know the seed.
        ports = list(range(9121, 9127))
        peers = [Peer(ports[0], max_peers=3, log_dir=self.log_dir)]
        peers += [Peer(p, seeds=[ports[0]], max_peers=3, log_dir=self.log_dir) for p in ports[1:]]
        for p in peers:
            p.start()
            time.sleep(0.05)
        time.sleep(1)
        links = {p.port: p.linked_ports() for p in peers}
        opened = {p.port: len(p.outgoing) for p in peers}
        for p in peers:
            p.stop()

        for count in opened.values():
            self.assertLessEqual(count, 3)
        # Some newcomer must have linked to a peer other than the seed.
        found = any(linked - {ports[0]} for port, linked in links.items() if port != ports[0])
        self.assertTrue(found)

    def test_dead_peer_is_logged_as_fail(self):
        a = Peer(9131, log_dir=self.log_dir)
        a.start()
        a.connect(9139)  # nothing listens on 9139
        a.stop()
        self.assertIn(("fail", 9139), [(e["event"], e["peer"]) for e in read_log(self.log_dir, 9131)])


    def test_bots_use_rendezvous_peers(self):
        ports = list(range(9141, 9154))
        roles = ["benign"] + ["bot", "benign"] * 6
        rendezvous = [9142 + 1, 9142 + 3, 9142 + 5]  # three benign peers
        peers = [Peer(p, r, seeds=[] if i == 0 else [ports[0]], max_peers=3,
                      exchange_interval=0.2, churn=0.5, log_dir=self.log_dir,
                      rendezvous_peers=rendezvous if r == "bot" else (),
                      rendezvous_preference=1.0)
                 for i, (p, r) in enumerate(zip(ports, roles))]
        for p in peers:
            p.start()
            time.sleep(0.05)
        time.sleep(2)
        bot_links = [q for p in peers if p.role == "bot" for q in p.outgoing.values()]
        for p in peers:
            p.stop()

        self.assertTrue(bot_links)
        self.assertGreaterEqual(sum(q in rendezvous for q in bot_links) / len(bot_links), 0.8)

    def test_exchange_rounds_fill_early_peers(self):
        # Without exchange rounds, the first newcomer finds nobody to connect to.
        ports = list(range(9161, 9171))
        peers = [Peer(ports[0], log_dir=self.log_dir)]
        peers += [Peer(p, seeds=[ports[0]], max_peers=3, exchange_interval=0.2,
                       log_dir=self.log_dir) for p in ports[1:]]
        for p in peers:
            p.start()
            time.sleep(0.05)
        time.sleep(1.5)
        first_newcomer = len(peers[1].outgoing)
        for p in peers:
            p.stop()
        self.assertGreater(first_newcomer, 0)


if __name__ == "__main__":
    unittest.main()