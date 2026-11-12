"""Milestone 6 – Distributed lock service.

Exposes a ResourceManager over TCP so worker *processes* – on the same VM or
on other nodes (e.g. `spoiltbrat`) – contend for shared resources hosted on
the core node (`godfather`). The service owns the global resource-allocation
graph, so deadlock detection/prevention works across machines.

Protocol (JSON lines, one connection per worker process):
  {"op":"REGISTER","pid":..,"priority":..}   -> {"ok":true}
  {"op":"ACQUIRE","pid":..,"res":..}         -> {"ok":true} | {"ok":false,"error":"VICTIM"|"ORDER",...}
  {"op":"RELEASE","pid":..,"res":..}         -> {"ok":true}
  {"op":"RELEASE_ALL","pid":..,"wasted":b}   -> {"ok":true}
  {"op":"RAG"} / {"op":"METRICS"} / {"op":"CYCLE"}
A dropped connection releases everything that process held (crash cleanup).

Run on the core node:
  python3 lock_server.py --strategy detect --resources config_db telemetry_log routing_table
"""
import argparse
import socket
import threading
import time

from resource_manager import DeadlockVictim, OrderViolation, ResourceManager
from txn_common import Channel, ChannelClosed

DEFAULT_LOCK_PORT = 9200


class LockServer:
    def __init__(self, rm: ResourceManager, host="0.0.0.0", port=DEFAULT_LOCK_PORT):
        self.rm, self.host, self.port = rm, host, port
        self._sock = None

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(64)
        threading.Thread(target=self._accept, daemon=True).start()
        return self

    def stop(self):
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()
        self.rm.stop()

    def _accept(self):
        while True:
            try:
                s, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(Channel(s),), daemon=True).start()

    def _serve(self, ch):
        ch.settimeout(None)
        pids = set()
        try:
            while True:
                m = ch.recv()
                op = m.get("op")
                if op == "REGISTER":
                    pids.add(m["pid"])
                    self.rm.register(m["pid"], m.get("priority", 0))
                    ch.send({"ok": True, "resources": self.rm.resources})
                elif op == "ACQUIRE":
                    try:
                        self.rm.acquire(m["pid"], m["res"])
                        ch.send({"ok": True})
                    except DeadlockVictim as e:
                        ch.send({"ok": False, "error": "VICTIM", "msg": str(e)})
                    except OrderViolation as e:
                        ch.send({"ok": False, "error": "ORDER", "msg": str(e)})
                elif op == "RELEASE":
                    self.rm.release(m["pid"], m["res"])
                    ch.send({"ok": True})
                elif op == "RELEASE_ALL":
                    self.rm.release_all(m["pid"], m.get("wasted", False))
                    ch.send({"ok": True})
                elif op == "RAG":
                    ch.send({"ok": True, "rag": self.rm.rag(), "text": self.rm.render_rag()})
                elif op == "CYCLE":
                    ch.send({"ok": True, "cycle": self.rm.find_cycle()})
                elif op == "METRICS":
                    ch.send({"ok": True, "metrics": self.rm.metrics()})
        except (ChannelClosed, OSError):
            pass
        finally:
            for p in pids:                       # crashed / finished client
                self.rm.release_all(p)
            ch.close()


class RemoteResourceManager:
    """Client stub with the same acquire/release API as ResourceManager."""

    def __init__(self, host, port=DEFAULT_LOCK_PORT):
        self.ch = Channel.connect(host, port, timeout=10)
        self.ch.settimeout(None)
        self._mu = threading.Lock()
        self.resources = []

    def _call(self, **msg):
        with self._mu:
            self.ch.send(msg)
            return self.ch.recv()

    def register(self, pid, priority=0):
        self.resources = self._call(op="REGISTER", pid=pid, priority=priority)["resources"]

    @property
    def order(self):
        return {r: i for i, r in enumerate(self.resources)}

    def acquire(self, pid, res):
        r = self._call(op="ACQUIRE", pid=pid, res=res)
        if not r["ok"]:
            raise (DeadlockVictim if r["error"] == "VICTIM" else OrderViolation)(r["msg"])

    def release(self, pid, res):
        self._call(op="RELEASE", pid=pid, res=res)

    def release_all(self, pid, wasted=False):
        self._call(op="RELEASE_ALL", pid=pid, wasted=wasted)

    def rag_text(self):
        return self._call(op="RAG")["text"]

    def find_cycle(self):
        return self._call(op="CYCLE")["cycle"]

    def metrics(self):
        return self._call(op="METRICS")["metrics"]

    def close(self):
        self.ch.close()


def main():
    ap = argparse.ArgumentParser(description="Distributed lock service (Milestone 6)")
    ap.add_argument("--port", type=int, default=DEFAULT_LOCK_PORT)
    ap.add_argument("--strategy", choices=["none", "detect", "prevent"], default="detect")
    ap.add_argument("--policy", choices=["fifo", "priority", "aging"], default="fifo")
    ap.add_argument("--resources", nargs="+",
                    default=["config_db", "telemetry_log", "routing_table"])
    a = ap.parse_args()
    rm = ResourceManager(a.resources, a.strategy, a.policy)
    LockServer(rm, port=a.port).start()
    print(f"[LOCK-SERVER] port {a.port} | strategy={a.strategy} policy={a.policy} "
          f"| resources={a.resources}")
    try:
        while True:
            time.sleep(5)
            print(rm.render_rag("live RAG"), flush=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
