import argparse
import csv
import itertools
import json
import multiprocessing
import os
import time

from analysis.analyze import analyze
from peer.launch import run


def run_names_done(results_path):
    if not os.path.exists(results_path):
        return set()
    with open(results_path) as f:
        return {row["run"] for row in csv.DictReader(f)}


def append_row(results_path, row):
    new = not os.path.exists(results_path)
    os.makedirs(os.path.dirname(results_path) or ".", exist_ok=True)
    with open(results_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new:
            writer.writeheader()
        writer.writerow(row)


def sweep(plan):
    combos = list(itertools.product(plan["benign_per_bot"], plan["rendezvous_preference"],
                                    range(1, plan["repeats"] + 1)))
    done = run_names_done(plan["results"])
    print(f"{len(combos)} runs planned, {len(done)} already in {plan['results']}.")

    for i, (per_bot, preference, repeat) in enumerate(combos, 1):
        name = f"b{per_bot}_s{preference}_r{repeat}"
        if name in done:
            continue
        config = {
            "bots": plan["bots"],
            "benign": plan["bots"] * per_bot,
            "duration": plan["duration"],
            "log_dir": os.path.join(plan["log_root"], name),
            "base_port": plan.get("base_port", 20000),
            "random_seed": repeat,
            "rendezvous_peers": plan["rendezvous_peers"],
            "all": plan["all"],
            "bot_settings": {"rendezvous_preference": preference},
        }
        print(f"[{i}/{len(combos)}] {name}: {config['bots']} bots, {config['benign']} benign")
        # Each run gets its own process, so nothing is left over between runs.
        process = multiprocessing.Process(target=run, args=(config,))
        process.start()
        process.join()

        result = analyze(config["log_dir"], plan.get("window", 15.0))
        result["run"] = name
        result["repeat"] = repeat
        append_row(plan["results"], result)
        time.sleep(plan.get("pause", 2))  # let the ports close before the next run

    print(f"Done. Results in {plan['results']}")


def main():
    parser = argparse.ArgumentParser(description="Run every combination in a sweep file.")
    parser.add_argument("plan", help="path to a JSON sweep file")
    args = parser.parse_args()
    with open(args.plan) as f:
        sweep(json.load(f))


if __name__ == "__main__":
    main()