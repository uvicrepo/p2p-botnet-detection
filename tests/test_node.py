import time
import unittest

from peer.node import Peer


class TestTwoPeers(unittest.TestCase):
    def test_hello_ping_pong(self):
        a = Peer("A", 9101, ping_interval=0.1)
        b = Peer("B", 9102, ping_interval=0.1)
        a.listen()
        b.listen()
        b.connect(9101)
        time.sleep(0.5)
        a.stop()
        b.stop()

        # A hears HELLO then PINGs from B. B hears HELLO then PONGs from A.
        self.assertEqual(a.received[0], ("HELLO", "B"))
        self.assertEqual(b.received[0], ("HELLO", "A"))
        self.assertIn(("PING", "B"), a.received)
        self.assertIn(("PONG", "A"), b.received)


if __name__ == "__main__":
    unittest.main()