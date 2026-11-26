import argparse
import socket
import threading
import time

from peer import messages

HOST = "127.0.0.1"


class Peer:
    def __init__(self, node_id, port, ping_interval=2.0):
        self.node_id = node_id
        self.port = port
        self.ping_interval = ping_interval
        self.received = []  # (type, sender), used by the test
        self.running = True
        self.server = None

    def send(self, sock, msg_type):
        messages.send(sock, {"type": msg_type, "id": self.node_id})

    def listen(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((HOST, self.port))
        self.server.listen()
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running:
            try:
                sock, _ = self.server.accept()
            except OSError:
                break  # server socket was closed
            threading.Thread(target=self._handle, args=(sock, False), daemon=True).start()

    def connect(self, port):
        sock = socket.create_connection((HOST, port))
        self.send(sock, "HELLO")
        threading.Thread(target=self._handle, args=(sock, True), daemon=True).start()
        threading.Thread(target=self._ping_loop, args=(sock,), daemon=True).start()

    def _ping_loop(self, sock):
        while self.running:
            time.sleep(self.ping_interval)
            try:
                self.send(sock, "PING")
            except OSError:
                break  # connection closed

    def _handle(self, sock, opened_by_me):
        with sock:
            while self.running:
                try:
                    message = messages.receive(sock)
                except (ConnectionError, OSError, ValueError):
                    break
                msg_type, sender = message["type"], message["id"]
                self.received.append((msg_type, sender))
                print(f"[{self.node_id}] got {msg_type} from {sender}")
                if msg_type == "HELLO" and not opened_by_me:
                    self.send(sock, "HELLO")
                elif msg_type == "PING":
                    self.send(sock, "PONG")

    def stop(self):
        self.running = False
        if self.server:
            self.server.close()


def main():
    parser = argparse.ArgumentParser(description="Run one peer.")
    parser.add_argument("--id", required=True, help="name of this peer")
    parser.add_argument("--port", type=int, required=True, help="port to listen on")
    parser.add_argument("--connect", type=int, help="port of a peer to connect to")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between PINGs")
    args = parser.parse_args()

    peer = Peer(args.id, args.port, args.interval)
    peer.listen()
    if args.connect:
        peer.connect(args.connect)
    print(f"[{args.id}] listening on port {args.port}. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        peer.stop()


if __name__ == "__main__":
    main()