import argparse
import glob
import json
import os
import random
import resource
import time

from peer.node import Peer

# Settings each peer gets unless its role overrides them.
DEFAULTS = {
    "max_peers": 10,
    "ping_interval": 5.0,
    "jitter": 0.5,
    "exchange_interval": 5.0,
    "rendezvous_preference": 0.0,
    "churn": 0.0,
}


def raise_file_limit():
    # Each peer needs a log file and several sockets.
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < hard:
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))


def run(config):
    random.seed(config.get("random_seed"))
    log_dir = config["log_dir"]
    os.makedirs(log_dir, exist_ok=True)
    for old in glob.glob(os.path.join(log_dir, "*.jsonl")):
        os.remove(old)

    # Shuffle roles so bots and benign peers join in random order.
    roles = ["bot"] * config["bots"] + ["benign"] * config["benign"]
    random.shuffle(roles)

    base = config.get("base_port", 20000)
    if base + len(roles) > 32768:
        # Linux uses ports from 32768 up for outgoing connections.
        raise ValueError("peer ports must stay below 32768")
    seed_port = base

    # Pick the rendezvous peers the bots all know, from the benign peers.
    benign_ports = [base + i for i, role in enumerate(roles) if role == "benign"]
    rendezvous = sorted(random.sample(benign_ports, min(config.get("rendezvous_peers", 20), len(benign_ports))))
    config = {**config, "rendezvous_ports": rendezvous}
    with open(os.path.join(log_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    peers = []
    for i, role in enumerate(roles):
        settings = {**DEFAULTS, **config.get("all", {}), **config.get(f"{role}_settings", {})}
        seeds = [] if i == 0 else [seed_port]
        if role == "bot":
            settings["rendezvous_peers"] = rendezvous
        peers.append(Peer(base + i, role, seeds, log_dir=log_dir, **settings))

    raise_file_limit()
    print(f"Starting {len(peers)} peers ({config['bots']} bots, {config['benign']} benign).")
    # Open every port first, so no peer tries to reach one that is not listening yet.
    for peer in peers:
        peer.listen()
    for peer in peers:
        peer.start()
        time.sleep(config.get("join_gap", 0.01))

    print(f"All peers running. Waiting {config['duration']} s.")
    time.sleep(config["duration"])

    # Tell every peer to stop first, so none of them logs failed
    # connections to peers that have already shut down.
    for peer in peers:
        peer.running = False
    for peer in peers:
        peer.stop()
    print(f"Done. Logs in {log_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Run many peers from a settings file.")
    parser.add_argument("config", help="path to a JSON settings file")
    args = parser.parse_args()
    with open(args.config) as f:
        run(json.load(f))


if __name__ == "__main__":
    main()