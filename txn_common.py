"""Shared plumbing for the Milestone 5 transaction subsystem.

* ``Channel``       – newline-delimited JSON messages over a TCP socket.
* ``WriteAheadLog`` – append-only, fsync'd JSON-lines log used for durability
                      and crash recovery by both coordinator and participants.
"""
import json
import os
import socket
import threading
import time

DEFAULT_TXN_PORT = 9100  # 9999 is used by coordination_protocol.py (Milestone 4)


class ChannelClosed(Exception):
    """Peer closed the connection (or we simulated a crash)."""


class Channel:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buf = b""

    @classmethod
    def connect(cls, host: str, port: int, timeout: float) -> "Channel":
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)
        return cls(sock)

    def settimeout(self, timeout):
        self.sock.settimeout(timeout)

    def send(self, msg: dict) -> None:
        try:
            self.sock.sendall((json.dumps(msg) + "\n").encode())
        except OSError as e:
            raise ChannelClosed(str(e)) from e

    def recv(self) -> dict:
        """Blocking read of one message. Raises socket.timeout or ChannelClosed."""
        while b"\n" not in self._buf:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                raise
            except OSError as e:
                raise ChannelClosed(str(e)) from e
            if not chunk:
                raise ChannelClosed("peer closed connection")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class WriteAheadLog:
    """Append-only JSON-lines log. Every record is fsync'd before returning,
    so anything written survives a process crash (the D in ACID)."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def append(self, record: dict) -> None:
        record = {"ts": time.time(), **record}
        with self._lock, open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def records(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        break  # torn final write after a crash: ignore the tail
        return out

    def latest_state_per_txn(self) -> dict:
        """txid -> list of records for that transaction, in log order."""
        txns = {}
        for r in self.records():
            if "txid" in r:
                txns.setdefault(r["txid"], []).append(r)
        return txns


def parse_addr(text: str, default_port: int = DEFAULT_TXN_PORT):
    if ":" in text:
        host, port = text.rsplit(":", 1)
        return host, int(port)
    return text, default_port
