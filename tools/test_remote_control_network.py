"""Real local Go platform/helpers + Python remote authority. No public messages."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "agent-comm-platform" / "agent-comm"
sys.path[:0] = [str(SDK / "python"), str(SDK / "tools")]
from agent_comm_runtime.remote import PROTOCOL, RemoteBridge
from agent_comm_runtime.store import Store
from agent_comm_runtime.transport import HelperTransport
from test_helper_platform import port, request, until


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--helper", type=Path, required=True)
    cli.add_argument("--platform", type=Path, required=True)
    args = cli.parse_args()
    folder = ROOT / "build" / "early-access" / "remote-network-test" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    ports = {name: port() for name in ("platform", "agent", "console")}
    urls = {name: f"http://127.0.0.1:{value}" for name, value in ports.items()}
    config = folder / "config.yaml"
    base = folder.as_posix()
    config.write_text(f"""platform:
  data_dir: '{base}/data'
identity:
  keys_dir: '{base}/data/keys'
libp2p:
  listen_addrs: ['/ip4/127.0.0.1/tcp/0']
relay:
  enabled: false
registry:
  persist_db: '{base}/data/registry.db'
mq:
  db_path: '{base}/data/mq.db'
api:
  listen_addr: '127.0.0.1:{ports['platform']}'
  rate_limit_rate: 0
""", encoding="utf-8")
    processes, logs = [], []
    bridge = store = None

    def start(name):
        log = (folder / f"{name}.log").open("ab")
        logs.append(log)
        command = [str(args.platform.resolve()), "-config", str(config)] if name == "platform" else [
            str(args.helper.resolve()), "daemon", str(folder / f"keys-{name}"), urls["platform"], str(ports[name])]
        processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        return until(lambda: request(urls[name], "/healthz" if name == "platform" else "/info"), name, timeout=35)

    def iso(seconds):
        return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

    try:
        start("platform")
        agent, console = start("agent"), start("console")
        for identity in (agent, console):
            until(lambda: request(urls["platform"], "/api/v1/registry/resolve?urn=" + identity["urn"]).get("found"), "registry")
        incoming, outgoing = HelperTransport(urls["agent"]), HelperTransport(urls["console"])
        store = Store(folder / "collaboration.sqlite3", local_urn=agent["urn"])
        owner = "network-test-owner|native-session"
        prepared = store.prepare_contact("test-contact", ["本机保存的联系人"], console["urn"], owner)
        lease = store.begin_confirmation(prepared["approval_id"], owner)
        store.finish_confirmation(prepared["approval_id"], lease["token"], owner, "同意")
        bridge = RemoteBridge(folder / "remote.sqlite3", store, agent["urn"])
        bridge.pair(console["urn"], "network-test-owner", ["capabilities", "contacts.list"], iso(3600))

        def roundtrip(method, restart=False):
            nonlocal bridge
            rid = str(uuid.uuid4())
            packet = {"protocol": PROTOCOL, "type": "request", "request_id": rid, "method": method,
                      "params": {}, "agent_urn": agent["urn"], "console_urn": console["urn"], "deadline": iso(120)}
            body = {"message_id": rid, "recipient_urn": agent["urn"], "text": json.dumps(packet),
                    "kind": "control.request", "conversation_id": "control:" + rid, "deadline": packet["deadline"]}
            assert outgoing.store(body)["success"]
            message = until(lambda: next((m for m in incoming.retrieve() if m["message_id"] == rid), None), "control arrival")
            assert message["sender_urn"] == console["urn"]
            # Native inbox must not ACK or ingest control messages before the bridge.
            store.sync_inbox(incoming)
            assert any(m["message_id"] == rid for m in incoming.retrieve())
            first_response = bridge.handle(message)
            if restart:
                bridge.close()
                bridge = RemoteBridge(folder / "remote.sqlite3", store, agent["urn"])
                assert bridge.handle(message) == first_response
            bridge.process(message, incoming)
            reply = until(lambda: next((m for m in outgoing.retrieve() if m.get("in_reply_to") == rid), None), "response arrival")
            assert reply["sender_urn"] == agent["urn"] and reply["deadline"] == packet["deadline"]
            response = json.loads(reply["text"])
            for key in ("request_id", "method", "agent_urn", "console_urn", "deadline"):
                assert response[key] == packet[key]
            assert response["type"] == "response" and response["protocol"] == PROTOCOL
            outgoing.ack([reply["message_id"]])
            assert not any(m["message_id"] == rid for m in incoming.retrieve())
            return response

        caps = roundtrip("capabilities")
        assert any(x["name"] == "contacts.list" and x["available"] for x in caps["result"]["methods"])
        contacts = roundtrip("contacts.list", restart=True)
        assert contacts["result"]["contacts"][0]["aliases"] == ["本机保存的联系人"]
        assert roundtrip("inbox.list")["error"]["code"] == "method_not_allowed"
        bridge.revoke(console["urn"])
        assert roundtrip("contacts.list")["error"]["code"] == "not_paired"
        report = {"result": "PASS", "checks": ["real signed encrypted control roundtrip", "agent-owned contacts",
            "native inbox leaves control requests unacknowledged", "bridge restart preserves immutable response",
            "method scope enforced", "local revocation enforced"], "logs": str(folder),
            "scope": "Fresh local identities and real Go processes; no production messages or model calls"}
        (folder / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if bridge:
            bridge.close()
        if store:
            store.close()
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
