import json
import os
import tempfile
import unittest

from analysis.analyze import analyze, auc


def write_run(run_dir, edges, roles, shared=(), ts=100.0):
    lines = {n: [] for n in roles}
    for a, b in edges:
        lines[b].append({"ts": ts, "node": b, "event": "ping", "peer": a, "bytes": 10, "role": roles[b]})
        lines[a].append({"ts": ts, "node": a, "event": "pong", "peer": b, "bytes": 10, "role": roles[a]})
    for n, entries in lines.items():
        entries.append({"ts": ts, "node": n, "event": "hello", "peer": n, "bytes": 10, "role": roles[n]})
        with open(os.path.join(run_dir, f"{n}.jsonl"), "w") as f:
            f.writelines(json.dumps(e) + "\n" for e in entries)
    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump({"shared_ports": list(shared), "bot_settings": {"shared_preference": 1.0}}, f)


class TestAuc(unittest.TestCase):
    def test_perfect_reversed_and_tied(self):
        self.assertEqual(auc([3, 4], [1, 2]), 1.0)
        self.assertEqual(auc([1, 2], [3, 4]), 0.0)
        self.assertEqual(auc([5, 5], [5, 5]), 0.5)


class TestAnalyze(unittest.TestCase):
    def test_tight_botnet_is_found(self):
        # 5 bots all linked to each other, 15 benign peers in a ring,
        # and one link between the two groups.
        bots = list(range(1, 6))
        benign = list(range(6, 21))
        roles = {**{n: "bot" for n in bots}, **{n: "benign" for n in benign}}
        edges = [(a, b) for i, a in enumerate(bots) for b in bots[i + 1:]]
        edges += [(benign[i], benign[(i + 1) % len(benign)]) for i in range(len(benign))]
        edges.append((bots[0], benign[0]))
        run_dir = tempfile.mkdtemp()
        write_run(run_dir, edges, roles)

        result = analyze(run_dir, window=15)
        self.assertEqual(result["bots"], 5)
        self.assertEqual(result["degree_auc"], 1.0)
        self.assertGreater(result["mutual_contacts_auc"], 0.9)
        self.assertEqual(result["best_community_f1"], 1.0)

    def test_bots_sharing_benign_peers(self):
        # 5 bots, not linked to each other, all linked to the same 3 benign
        # peers. 15 benign peers in a ring. Bots share contacts, so mutual
        # contacts finds them, but they do not have more links than others.
        bots = list(range(1, 6))
        benign = list(range(6, 21))
        shared = benign[:3]
        roles = {**{n: "bot" for n in bots}, **{n: "benign" for n in benign}}
        edges = [(b, s) for b in bots for s in shared]
        edges += [(benign[i], benign[(i + 1) % len(benign)]) for i in range(len(benign))]
        run_dir = tempfile.mkdtemp()
        write_run(run_dir, edges, roles, shared)

        result = analyze(run_dir, window=15)
        self.assertEqual(result["measured_sharing"], 1.0)
        self.assertLess(result["degree_auc"], 0.9)
        self.assertGreater(result["mutual_contacts_auc"], 0.9)


if __name__ == "__main__":
    unittest.main()