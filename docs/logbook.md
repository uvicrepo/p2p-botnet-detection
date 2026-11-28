# Project Logbook

How Bot Behaviour Affects Structure-Based Detection of P2P Botnets

CSC579, Fall 2026

This logbook records the work done on the project, in date order. Each entry lists what was done, what was tested, and what comes next.

---
---
## 2026-11-27

### Done

- Added `experiments/sweep.py`. Runs every combination in a sweep plan and writes one results row per run.
- Ran the first sweep: 20 bots, 32 runs. Results in `results/sweep.csv`.
- Renamed shared peers to rendezvous peers in the code.
- Removed Louvain community detection from the analysis.
- Analysis now measures dilution (share of the bots' neighbours that are ordinary benign peers) and average neighbour overlap for bots and benign peers.
- New settings: 40 bots, 20 rendezvous peers, 10 links opened per peer.
- Launcher now opens every port before peers connect. This removed failed connections at startup.
- Started the second sweep: `configs/sweep_dilution.json` and `configs/sweep_ratio.json`.

### Tested

`python3 -m unittest discover -v`: 16 tests, all passed.

### Next

Charts from the second sweep.

---
## 2026-11-26

### Done

- Added `analysis/analyze.py`. Builds a communication graph from one run's logs and scores degree, mutual contacts, and Louvain communities against the true roles.
- Changed the bot model. Bots no longer prefer other bots. They connect to a fixed set of shared benign peers instead, set by `shared_preference`.
- Added `.gitignore` for logs, Python cache, and the virtual environment.
- Added `peer/launch.py` and `configs/example.json`. Starts many peers in one program from a settings file.

### Tested

`python3 -m unittest discover -v`: 15 tests, all passed.

### Next

Experiments.

---
## 2026-11-25

### Done

Peer program:

- Added `peer/node.py`, a threaded peer. It replaces `peer/peer.py` from 2026-10-21. It uses `peer/messages.py` for all sending and receiving.
- Two peers exchange HELLO, then the peer that opened the connection sends PING at a set interval and the other answers PONG.
- Peer discovery. A new peer contacts a seed only to get a list of peers (PEERS), then hangs up. It then connects to peers from that list until it reaches its peer-list size. Every peer accepts incoming connections and shares a random sample of up to 20 peers it has heard of.
- JSON line logging. Each peer writes `logs/<port>.jsonl`. Each line has timestamp, node, event, peer, bytes, and role (bot or benign). Events: connect, fail, hello, peers, ping, pong.
- A peer is identified by its port number.
- Added an empty `tests/__init__.py` so `unittest discover` finds the tests.

Research:

- Verified the Holz et al. Storm reference against the paper. Title, authors, and venue (USENIX LEET 2008) are correct. The paper gives no values for any of the five bot settings.
- Reviewed Mahboubi et al. (Internet of Things, 2025). Useful as background. No values for the settings.
- Checked the TNT paper (Zhao et al.). It compares topology-only detection with no benign P2P peers against one fixed amount (about 10K of 140K nodes). It does not vary the amount of benign traffic.

Change of research direction:

- The main experiment changes from sweeping five bot settings to dilution: how many benign peers, and how much mixing between bots and benign peers, it takes before structure-based detection can no longer separate the botnet. The idea came from a classmate's question on 2026-11-20. It extends TNT's two-point comparison into a curve.
- Draft research question: How many legitimate P2P peers, and how much mixing between bots and legitimate peers, does it take before structure-based detection can no longer separate a P2P botnet?
- Detection stays structure-based with no machine learning: degree, density, mutual contacts, Louvain community detection.

### Tested

Unit tests: `python3 -m unittest discover -v`

Result: 9 tests ran, all passed (3 framing, 2 messages, 4 node). The node tests cover HELLO, PING, and PONG, log line fields, discovery through a seed, and logging a failed connection to a dead peer.


### Notes

- The first discovery version turned peers away when full. Newcomers ran out of peers to try and the network split into 44 separate pieces. Fixed by limiting only the connections a peer opens itself and always accepting incoming ones.
- The first few peers to join open no connections themselves, and early peers collect more incoming links. A periodic peer exchange round should fix this.
- Peers will run as threads in one program, each on its own port, so up to about 1,000 peers fit on one computer.
- Times will be scaled down (for example 1 s in the program stands for 10 s) so each run takes minutes. The report must state this.
- `peer/peer.py` is no longer used.

### Next

Settings file and launcher: start many peers in one program, with role, peer-list size, periodic peer exchange, and the bot-to-bot mixing setting.
---
## 2026-11-20

### Done

- Responded to classmates' questions on the project update.

- The discussion gave a useful idea for improving the project: change the ratio of bots to normal peers and measure how much harder detection gets.


### Next

Finish the peer program. Consider the bot to normal peer ratio as an experiment.

---

## 2026-11-18

### Done

- Reviewed classmates' project updates and gave feedback.

---

## 2026-11-16

### Done

- Submitted the midterm project update. Research question and approach unchanged from the proposal.
- Reported progress: repository and website set up, message framing complete and tested.
- Adjustments reported: peer overlap needs a measurable definition, a source for the legitimate peer settings is still being chosen, and the Holz et al. Storm reference is being checked against the paper.
- Revised schedule: finish the peer program Nov 17 to 24, then starting values, analysis code, and experiments Nov 25 to Dec 1, then report, presentation, and website.

### Next

Finish the peer program: discovery, peer list exchange, heartbeats, logging, and settings.


### 2026-10-21

### Done

- Added `peer/messages.py`. It turns a message (a small dictionary) into bytes with JSON and sends it through the framing layer, and reads one message back.
- Added `peer/peer.py`. A minimal peer that either listens on a local port or sends a PING to another peer. A listener greets each connection with HELLO and replies to a PING with a PONG.
- Added `tests/test_messages.py` with two tests.

### Tested

Unit tests: `python3 -m unittest -v tests.test_messages tests.test_framing`

Result: 5 tests ran, all passed.

Live check with two peers:

1. In one terminal: `python3 -m peer.peer listen 9001`
2. In another: `python3 -m peer.peer ping 127.0.0.1 9001`

The pinger printed received HELLO then received PONG. The listener printed received HELLO then received PING. The full handshake works between two separate programs over a real port.

### Notes
- Messages are JSON, so they are easy to read in logs and easy to extend later (for example, HELLO carrying a node id and port).
- The peer is single-threaded and handles one connection at a time. Threads and timers come later, with check-in intervals.

### Next

Seed list and PEERS exchange, so peers can find each other.

---

## 2026-10-13

### Done

- Added `peer/framing.py`. It wraps each message with a 4-byte length prefix and a SHA-256 hash, and reads one complete message back from a connection. Messages with a wrong hash are rejected. Frames larger than 1 MB are also rejected.
- Added `tests/test_framing.py` with three tests using Python's built-in unittest module.

### Tested

Command: `python3 -m unittest -v tests.test_framing`

Result: 3 tests ran, all passed.

1. A message comes through unchanged.
2. Two messages sent together are read back as two separate messages.
3. A message with one changed byte is rejected.

### Notes

- The length prefix and SHA-256 check come from the peer program spec in the definition document.
- The tests use a socket pair inside one program, not two separate programs on a real port.
- A message arriving in pieces is not really tested yet.

### Next

Two peers on local ports exchanging HELLO, PING, and PONG.