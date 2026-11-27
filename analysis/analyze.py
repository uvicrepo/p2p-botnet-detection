import argparse
import csv
import glob
import json
import os
import statistics

import networkx as nx


def load_run(run_dir):
    rows = []
    for path in glob.glob(os.path.join(run_dir, "*.jsonl")):
        with open(path) as f:
            rows += [json.loads(line) for line in f]
    with open(os.path.join(run_dir, "config.json")) as f:
        config = json.load(f)
    return rows, config


def build_graph(rows, window):
    # An edge is a pair of peers that exchanged PING or PONG in the last
    # `window` seconds of the run. Short seed contacts are left out.
    roles = {r["node"]: r["role"] for r in rows}
    end = max(r["ts"] for r in rows)
    graph = nx.Graph()
    graph.add_nodes_from(roles)
    for r in rows:
        if r["event"] in ("ping", "pong") and r["ts"] >= end - window:
            graph.add_edge(r["node"], r["peer"])
    nx.set_node_attributes(graph, roles, "role")
    return graph


def auc(bot_scores, benign_scores):
    # Chance that a random bot scores higher than a random benign peer.
    # 1.0 means perfect separation, 0.5 means no better than a coin flip.
    wins = 0.0
    for b in bot_scores:
        for n in benign_scores:
            wins += 1.0 if b > n else 0.5 if b == n else 0.0
    return wins / (len(bot_scores) * len(benign_scores))


def mutual_contact_score(graph, node):
    # Average share of contacts this peer has in common with each of its
    # neighbours (Jaccard similarity of contact lists). A simplified version
    # of the mutual-contacts idea: bots in one botnet tend to share contacts.
    mine = set(graph[node])
    if not mine:
        return 0.0
    scores = []
    for other in mine:
        theirs = set(graph[other]) - {node}
        union = (mine - {other}) | theirs
        scores.append(len((mine - {other}) & theirs) / len(union) if union else 0.0)
    return statistics.mean(scores)


def louvain_scores(graph, bots, seed=1):
    communities = nx.community.louvain_communities(graph, seed=seed)
    # How bot-heavy is the community each bot lands in, compared with the
    # bot share of the whole network?
    community_of = {n: c for c in communities for n in c}
    bot_share = len(bots) / graph.number_of_nodes()
    purity = statistics.mean(len(community_of[b] & bots) / len(community_of[b]) for b in bots)
    # Best case: flag the single community with the most bots.
    best = max(communities, key=lambda c: len(c & bots))
    precision = len(best & bots) / len(best)
    recall = len(best & bots) / len(bots)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"communities": len(communities), "bot_purity": purity,
            "bot_share": bot_share, "best_community_f1": f1}


def ping_gaps(rows):
    # Time between PINGs on each link, to check the interval setting.
    times = {}
    for r in rows:
        if r["event"] == "ping":
            times.setdefault((r["node"], r["peer"]), []).append(r["ts"])
    gaps = []
    for ts in times.values():
        ts.sort()
        gaps += [b - a for a, b in zip(ts, ts[1:])]
    return gaps


def analyze(run_dir, window):
    rows, config = load_run(run_dir)
    graph = build_graph(rows, window)
    bots = {n for n, r in graph.nodes(data="role") if r == "bot"}
    benign = set(graph) - bots

    degree = dict(graph.degree())
    mutual = {n: mutual_contact_score(graph, n) for n in graph}
    bot_edges = [(a, b) for a, b in graph.edges() if a in bots or b in bots]
    bot_to_bot = sum(1 for a, b in bot_edges if a in bots and b in bots)
    gaps = ping_gaps(rows)
    settings = {**config.get("all", {}), **config.get("bot_settings", {})}

    result = {
        "run": os.path.basename(os.path.normpath(run_dir)),
        "bots": len(bots),
        "benign": len(benign),
        "benign_per_bot": len(benign) / len(bots),
        "bot_preference": settings.get("bot_preference", 0.0),
        "measured_mixing": bot_to_bot / len(bot_edges) if bot_edges else 0.0,
        "edges": graph.number_of_edges(),
        "density": nx.density(graph),
        "bot_density": nx.density(graph.subgraph(bots)),
        "benign_density": nx.density(graph.subgraph(benign)),
        "degree_auc": auc([degree[n] for n in bots], [degree[n] for n in benign]),
        "mutual_contacts_auc": auc([mutual[n] for n in bots], [mutual[n] for n in benign]),
        "mean_ping_gap": statistics.mean(gaps) if gaps else 0.0,
    }
    result.update(louvain_scores(graph, bots))
    return result


def main():
    parser = argparse.ArgumentParser(description="Analyse one run's logs.")
    parser.add_argument("run_dir", help="folder with one run's .jsonl logs and config.json")
    parser.add_argument("--window", type=float, default=15.0,
                        help="seconds at the end of the run to build the graph from")
    parser.add_argument("--csv", help="append the result as one row to this CSV file")
    args = parser.parse_args()

    result = analyze(args.run_dir, args.window)
    for key, value in result.items():
        print(f"{key:20} {value:.3f}" if isinstance(value, float) else f"{key:20} {value}")

    if args.csv:
        new = not os.path.exists(args.csv)
        os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
        with open(args.csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(result))
            if new:
                writer.writeheader()
            writer.writerow(result)


if __name__ == "__main__":
    main()