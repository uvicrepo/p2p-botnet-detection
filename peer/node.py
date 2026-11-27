import argparse
import json
import os
import random
import socket
import threading
import time

from peer import messages

HOST = "127.0.0.1"
PEERS_SAMPLE = 20  # how many known peers to share in one PEERS message


class Peer:
    # A peer is identified by its port number.
    def __init__(self, port, role="benign", seeds=(), max_peers=10,
                 ping_interval=2.0, jitter=0.0, exchange_interval=None,
                 shared_peers=(), shared_preference=0.0, churn=0.0, log_dir="logs"):
        self.port = port
        self.role = role
        self.seeds = list(seeds)
        self.max_peers = max_peers  # limit on connections this peer opens
        self.ping_interval = ping_interval
        self.jitter = jitter  # 0.5 means each wait is the interval plus or minus 50%
        self.exchange_interval = exchange_interval  # None means no periodic exchange
        # Bots all know the same few peers, like Storm bots searching the
        # same keys. shared_preference is the chance a bot picks one of them.
        self.shared_peers = set(shared_peers)
        self.shared_preference = shared_preference
        self.churn = churn  # fraction of opened links dropped each exchange round
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = open(os.path.join(log_dir, f"{port}.jsonl"), "a", buffering=1)
        self.outgoing = {}  # socket -> peer port, connections we opened
        self.incoming = {}  # socket -> peer port, connections others opened
        self.pending = set()  # ports we are connecting to
        self.tried = set()  # ports we have tried, so each is tried once
        self.known = set()  # every peer we have heard of
        self.lock = threading.Lock()
        self.running = True
        self.server = None

    def log(self, event, peer, size=0):
        line = json.dumps({"ts": time.time(), "node": self.port, "event": event,
                           "peer": peer, "bytes": size, "role": self.role})
        with self.lock:
            if not self.log_file.closed:
                self.log_file.write(line + "\n")

    def send(self, sock, msg_type, **fields):
        messages.send(sock, {"type": msg_type, "id": self.port, **fields})

    def _wait(self, interval):
        time.sleep(interval * (1 + random.uniform(-self.jitter, self.jitter)))

    def start(self):
        self.listen()
        for seed in self.seeds:
            self.bootstrap(seed)
        if self.exchange_interval:
            threading.Thread(target=self._exchange_loop, daemon=True).start()

    def listen(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((HOST, self.port))
        self.server.listen(128)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running:
            try:
                sock, _ = self.server.accept() # type: ignore
            except OSError:
                break
            threading.Thread(target=self._handle, args=(sock, "incoming"), daemon=True).start()

    def _full(self):
        return len(self.outgoing) + len(self.pending) >= self.max_peers

    def linked_ports(self):
        with self.lock:
            return set(self.outgoing.values()) | set(self.incoming.values())

    def _open(self, port):
        try:
            sock = socket.create_connection((HOST, port), timeout=2)
            sock.settimeout(None)
        except OSError:
            return None
        return sock

    def bootstrap(self, port):
        # Ask a seed for peers. This does not use a slot.
        sock = self._open(port)
        if not sock:
            self.log("fail", port)
            return
        self.send(sock, "HELLO", bootstrap=True)
        threading.Thread(target=self._handle, args=(sock, "bootstrap"), daemon=True).start()

    def connect(self, port):
        if not self.running:
            return
        with self.lock:
            if (port == self.port or port in self.tried or self._full()
                    or port in self.outgoing.values() or port in self.incoming.values()):
                return
            self.tried.add(port)
            self.pending.add(port)
        self._finish_connect(port)

    def _finish_connect(self, port):
        sock = self._open(port)
        with self.lock:
            self.pending.discard(port)
            if sock:
                self.outgoing[sock] = port
        if not sock:
            self.log("fail", port)
            return
        self.send(sock, "HELLO")
        threading.Thread(target=self._handle, args=(sock, "outgoing"), daemon=True).start()
        threading.Thread(target=self._ping_loop, args=(sock,), daemon=True).start()

    def fill(self):
        # Pick new peers from the ones we know until our list is full.
        if not self.running:
            return
        picks = []
        with self.lock:
            linked = set(self.outgoing.values()) | set(self.incoming.values())
            skip = linked | self.tried | {self.port}
            candidates = [p for p in self.known if p not in skip]
            shared = [p for p in self.shared_peers if p not in skip]
            while (candidates or shared) and not self._full():
                if shared and (not candidates or random.random() < self.shared_preference):
                    port = random.choice(shared)
                else:
                    port = random.choice(candidates)
                for pool in (candidates, shared):
                    if port in pool:
                        pool.remove(port)
                self.tried.add(port)
                self.pending.add(port)
                picks.append(port)
        for port in picks:
            threading.Thread(target=self._finish_connect, args=(port,), daemon=True).start()

    def _ping_loop(self, sock):
        while self.running and sock in self.outgoing:
            self._wait(self.ping_interval)
            try:
                self.send(sock, "PING")
            except OSError:
                break

    def _drop_some(self):
        with self.lock:
            links = list(self.outgoing.items())
        count = self.churn * len(links)
        count = int(count) + (random.random() < count - int(count))
        for sock, port in random.sample(links, count):
            self.log("drop", port)
            with self.lock:
                self.outgoing.pop(sock, None)
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def _exchange_loop(self):
        # Each round: drop some links (churn), swap peer lists with one
        # linked peer, then fill empty slots.
        while self.running:
            self._wait(self.exchange_interval)
            with self.lock:
                self.tried.clear()
            self._drop_some()
            with self.lock:
                socks = list(self.outgoing) + list(self.incoming)
            if socks:
                sock = random.choice(socks)
                try:
                    self.send(sock, "PEERS", peers=self._sample_known(None), ask=True)
                except OSError:
                    pass
            self.fill()

    def _sample_known(self, exclude):
        with self.lock:
            entries = [p for p in self.known if p != exclude]
        return random.sample(entries, min(PEERS_SAMPLE, len(entries)))

    def _handle(self, sock, mode):
        try:
            while self.running:
                message = messages.receive(sock)
                msg_type, sender = message["type"], message["id"]
                self.log(msg_type.lower(), sender, len(json.dumps(message)))
                with self.lock:
                    self.known.add(sender)

                if msg_type == "HELLO":
                    if message.get("bootstrap"):
                        # A newcomer only wants peers to try. Not a real link.
                        self.send(sock, "PEERS", peers=self._sample_known(sender))
                        break
                    if mode == "incoming":
                        with self.lock:
                            self.incoming[sock] = sender
                        self.send(sock, "HELLO")
                        self.send(sock, "PEERS", peers=self._sample_known(sender))
                    self.log("connect", sender)
                elif msg_type == "PEERS":
                    with self.lock:
                        self.known.update(message["peers"])
                    if message.get("ask"):
                        self.send(sock, "PEERS", peers=self._sample_known(sender))
                    self.fill()
                    if mode == "bootstrap":
                        break
                elif msg_type == "PING":
                    self.send(sock, "PONG")
        except (ConnectionError, OSError, ValueError, KeyError, TypeError):
            pass
        finally:
            with self.lock:
                self.outgoing.pop(sock, None)
                self.incoming.pop(sock, None)
            sock.close()

    def stop(self):
        self.running = False
        if self.server:
            self.server.close()
        with self.lock:
            socks = list(self.outgoing) + list(self.incoming)
        for sock in socks:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        with self.lock:
            self.log_file.close()


def main():
    parser = argparse.ArgumentParser(description="Run one peer.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--role", choices=["bot", "benign"], default="benign")
    parser.add_argument("--seeds", default="", help="comma-separated ports, e.g. 9001,9002")
    parser.add_argument("--max-peers", type=int, default=10)
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between PINGs")
    parser.add_argument("--exchange", type=float, default=None, help="seconds between peer exchange rounds")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s]
    peer = Peer(args.port, args.role, seeds, args.max_peers, args.interval,
                exchange_interval=args.exchange, log_dir=args.log_dir)
    peer.start()
    print(f"Peer {args.port} ({args.role}) running. Log: {args.log_dir}/{args.port}.jsonl. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        peer.stop()


if __name__ == "__main__":
    main()