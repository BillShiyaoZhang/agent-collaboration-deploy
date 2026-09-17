"""Real platform + two local helpers: agent-owned friendship and Web/native parity.

No external account, public message or model call is used. Each execution creates
fresh identities and databases under build/integration/agent-web-parity.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / "agent-comm-platform" / "agent-comm"
sys.path[:0] = [str(SDK / "python"), str(SDK / "tools")]
from agent_comm_runtime.remote import PROTOCOL, RemoteBridge
from agent_comm_runtime.store import Store
from agent_comm_runtime.transport import HelperTransport
from test_helper_platform import port, request, until


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", required=True, type=Path)
    parser.add_argument("--platform", required=True, type=Path)
    args = parser.parse_args()
    folder = ROOT / "build/integration/agent-web-parity" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    ports = {name: port() for name in ("platform", "alice", "bob", "console")}
    urls = {name: f"http://127.0.0.1:{number}" for name, number in ports.items()}
    config = folder / "config.yaml"
    config.write_text(f"""platform:
  data_dir: '{folder}/data'
identity:
  keys_dir: '{folder}/data/keys'
libp2p:
  listen_addrs: ['/ip4/127.0.0.1/tcp/0']
relay:
  enabled: false
registry:
  persist_db: '{folder}/data/registry.db'
mq:
  db_path: '{folder}/data/mq.db'
api:
  listen_addr: '127.0.0.1:{ports['platform']}'
  rate_limit_rate: 0
""", encoding="utf-8")
    processes, logs, stores, bridges = [], [], [], []
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PLATFORM_")}

    def start(name):
        log = (folder / f"{name}.log").open("ab")
        logs.append(log)
        command = [str(args.platform.resolve()), "-config", str(config)] if name == "platform" else [
            str(args.helper.resolve()), "daemon", str(folder / f"keys-{name}"), urls["platform"], str(ports[name])]
        processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=folder))
        return until(lambda: request(urls[name], "/healthz" if name == "platform" else "/info"), name, timeout=40)

    def local_action(store, method, params, owner):
        key = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        return store.remote_mutation(method, params, owner, request_key=key, fingerprint=key, valid_until=time.time()+120)

    def pump(store, transport, condition, description):
        def step():
            store.sync_inbox(transport)
            return condition()
        return until(step, description)

    results = []
    try:
        start("platform")
        identities = {name: start(name) for name in ("alice", "bob", "console")}
        for name, identity in identities.items():
            registered = request(urls[name], "/api/v1/platform/register", {})
            assert registered == {"registered": True, "urn": identity["urn"]}
        results.append("Binding automatically registers each original local identity with its own signature")
        alice, bob = [Store(folder / f"{name}.sqlite3", local_urn=identities[name]["urn"], owner_principal=name) for name in ("alice", "bob")]
        stores.extend([alice, bob])
        transports = {name: HelperTransport(urls[name]) for name in identities}
        owner_a, owner_b = "alice|native", "bob|native"
        expiry = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        bridge = RemoteBridge(folder / "remote.sqlite3", alice, identities["alice"]["urn"])
        bridges.append(bridge)
        bridge.pair(identities["console"]["urn"], "alice", ["contacts.add", "contacts.list", "contacts.requests", "messages.send", "inbox.mark_read", "attention.list"], expiry)

        def web_action(method, params):
            rid = str(uuid.uuid4())
            deadline = (datetime.now(timezone.utc)+timedelta(seconds=120)).isoformat()
            packet = {"protocol": PROTOCOL, "type": "request", "request_id": rid, "method": method, "params": params,
                      "agent_urn": identities["alice"]["urn"], "console_urn": identities["console"]["urn"], "deadline": deadline}
            transports["console"].store({"message_id": rid, "recipient_urn": identities["alice"]["urn"],
                "kind": "control.request", "conversation_id": "control:"+rid, "deadline": deadline, "text": json.dumps(packet)})
            message = until(lambda: next((m for m in transports["alice"].retrieve() if m["message_id"] == rid), None), "Web request")
            bridge.process(message, transports["alice"])
            response = until(lambda: next((m for m in transports["console"].retrieve() if m.get("in_reply_to") == rid), None), "Web response")
            result = json.loads(response["text"])
            assert "error" not in result, result
            transports["console"].ack([response["message_id"]])
            return result["result"]

        added = web_action("contacts.add", {"contact_id": "bob", "aliases": ["Bob"], "urn": identities["bob"]["urn"]})
        alice.flush_social_outbox(transports["alice"])
        pending = pump(bob, transports["bob"], lambda: bob.contact_requests(owner_b)["contact_requests"], "Unknown sender friend request")
        assert len(pending) == 1 and pending[0]["status"] == "pending"
        request_id = pending[0]["request_id"]
        assert added["request_id"] == request_id
        assert any(item["kind"] == "friend_request_received" and item["state"] == "open" for item in bob.attention(owner_b)["items"])
        local_action(bob, "contacts.respond", {"request_id": request_id, "decision": "accept"}, owner_b)
        bob.flush_social_outbox(transports["bob"])
        pump(alice, transports["alice"], lambda: alice.state(owner_a)["contacts"][0]["connection_status"] == "connected", "Accepted friend sync")
        assert web_action("contacts.list", {})["contacts"][0]["connection_status"] == "connected"
        assert bob.state(owner_b)["contacts"][0]["connection_status"] == "connected"
        assert not any(item["kind"] == "friend_request_received" and item["state"] == "open" for item in bob.attention(owner_b)["items"])
        results.append("Web friend request reaches an unknown peer, native acceptance connects both address books and resolves its alert")

        sent = web_action("messages.send", {"recipient_urn": identities["bob"]["urn"], "text": "Web to native"})
        alice.flush_social_outbox(transports["alice"])
        inbox = pump(bob, transports["bob"], lambda: next((m for m in bob.inbox(owner_b)["messages"] if m["message_id"] == sent["message_id"]), None), "Web message")
        assert inbox["text"] == "Web to native" and not inbox["read"]
        bob.mark_read(sent["message_id"], owner_b)
        assert next(m for m in bob.inbox("bob|remote:another-device")["messages"] if m["message_id"] == sent["message_id"])["read"]

        reply = local_action(bob, "messages.send", {"recipient_urn": identities["alice"]["urn"], "text": "Native to Web"}, owner_b)
        bob.flush_social_outbox(transports["bob"])
        pump(alice, transports["alice"], lambda: next((m for m in alice.inbox(owner_a)["messages"] if m["message_id"] == reply["message_id"]), None), "Native reply")
        web_action("inbox.mark_read", {"message_id": reply["message_id"]})
        assert next(m for m in alice.inbox(owner_a)["messages"] if m["message_id"] == reply["message_id"])["read"]
        assert all(item["state"] != "open" for item in alice.attention(owner_a)["items"] if item["subject_id"] == reply["message_id"])
        results.append("Web/native messages share the agent inbox and read decisions close the other surface's alert")

        alice.refresh_presence(transports["alice"])
        assert alice.state(owner_a)["contacts"][0]["presence"]["status"] == "online"
        results.append("Connected friends expose verified recent heartbeat presence through the local agent")
        report = {"status": "passed", "checks": results, "artifacts": str(folder)}
        (folder / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for bridge in bridges:
            bridge.close()
        for store in stores:
            store.close()
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
