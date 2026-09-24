"""Isolated v2 private/compliance process acceptance; never contacts public services.

Build the three binaries first, then run:
  python tests/integration/test_v2_gateway_network.py \
    --platform build/platform-test.exe --helper build/agent-comm-helper.exe \
    --policy-tool build/v2-policy.exe

Fresh identities, keys, SQLite files, and logs stay under ignored build/.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
SDK_TOOLS = ROOT / "agent-comm-platform" / "agent-comm" / "tools"
sys.path.insert(0, str(SDK_TOOLS))
from test_helper_platform import port, request, until  # noqa: E402


def run_cli(executable, *args):
    result = subprocess.run([str(executable), *map(str, args)], check=True,
                            capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--platform", type=Path, required=True)
    cli.add_argument("--helper", type=Path, required=True)
    cli.add_argument("--policy-tool", type=Path, required=True)
    args = cli.parse_args()
    platform, helper, policy_tool = (item.resolve() for item in
                                     (args.platform, args.helper, args.policy_tool))
    folder = ROOT / "build" / "integration" / "v2-gateway-network" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    ports = {name: port() for name in ("platform", "a", "b")}
    urls = {name: f"http://127.0.0.1:{number}" for name, number in ports.items()}
    keys = folder / "v2-keys"
    run_cli(policy_tool, "keygen", "--out-dir", keys)
    platform_keys = folder / "data" / "keys"
    platform_identity = run_cli(helper, "init", platform_keys)
    identities = {name: run_cli(helper, "init", folder / f"keys-{name}") for name in ("a", "b")}
    root_public_hex = (keys / "policy-root.public").read_bytes().hex()
    for name, other in (("a", "b"), ("b", "a")):
        local_dir = folder / f"keys-{name}"
        run_cli(helper, "v2-pin-policy-root", local_dir, root_public_hex,
                platform_identity["peer_id"],
                "Independent deployment root and Platform PeerID checked in isolated process test")
        run_cli(helper, "v2-pin-peer", local_dir, identities[other]["urn"],
                identities[other]["ed25519_pubkey"],
                "Peer full key compared over isolated local test channel")

    config = folder / "config.yaml"
    policy_file = folder / "policy.json"
    processes, logs = {}, []
    process_env = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("PLATFORM_")}

    def configure(mode, epoch):
        nonlocal policy_file
        policy_file = folder / f"policy-{epoch}.json"
        command = ["sign", "--keys-dir", keys,
                   "--platform-id", platform_identity["peer_id"],
                   "--mode", mode, "--epoch", epoch, "--out", policy_file]
        if mode == "private":
            command.append("--allow-v1")  # Staged migration keeps old clients usable.
        run_cli(policy_tool, *command)
        config.write_text(f"""platform:
  data_dir: '{(folder / 'data').as_posix()}'
identity:
  keys_dir: '{platform_keys.as_posix()}'
libp2p:
  listen_addrs: ['/ip4/127.0.0.1/tcp/0']
relay:
  enabled: false
registry:
  persist_db: '{(folder / 'data' / 'registry.db').as_posix()}'
mq:
  db_path: '{(folder / 'data' / 'mq.db').as_posix()}'
v2:
  enabled: true
  policy_file: '{policy_file.as_posix()}'
  policy_root_public_key_file: '{(keys / 'policy-root.public').as_posix()}'
  gateway_private_key_file: '{(keys / 'gateway.private').as_posix()}'
  receipt_private_key_file: '{(keys / 'receipt.private').as_posix()}'
api:
  listen_addr: '127.0.0.1:{ports['platform']}'
  rate_limit_rate: 0
""", encoding="utf-8")

    def start(name):
        log = (folder / f"{name}.log").open("ab")
        logs.append(log)
        command = ([str(platform), "-config", str(config)] if name == "platform" else
                   [str(helper), "daemon", str(folder / f"keys-{name}"),
                    urls["platform"], str(ports[name])])
        processes[name] = subprocess.Popen(command, cwd=folder, env=process_env,
                                           stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        return until(lambda: request(urls[name], "/healthz" if name == "platform" else "/info"),
                     name + " startup", timeout=40)

    def stop(name):
        process = processes.pop(name, None)
        if process is not None:
            process.kill()  # Include crash persistence in the acceptance path.
            process.wait(timeout=10)

    def registered(name):
        return until(lambda: request(urls["platform"],
                                     "/api/v1/registry/resolve?urn=" + identities[name]["urn"]).get("found"),
                     name + " registry", timeout=40)

    def inbox(name):
        return request(urls[name], "/api/v1/mq/retrieve")["messages"]

    def receive(name, message_id):
        return until(lambda: next((item for item in inbox(name)
                                   if item["message_id"] == message_id), None),
                     message_id + " verified delivery", timeout=60)

    def send(name, message_id, recipient, text):
        body = {"message_id": message_id, "recipient_urn": identities[recipient]["urn"],
                "text": text, "kind": "task", "conversation_id": "v2-test"}
        return until(lambda: request(urls[name], "/api/v2/mq/store", body),
                     message_id + " local acceptance", timeout=40)

    def disclosure(name, mode, epoch):
        def matching():
            state = request(urls[name], "/api/v2/disclosure")
            return state if state.get("mode") == mode and state.get("policy_epoch") == epoch else None
        return until(matching, name + " verified disclosure state", timeout=40)

    def queued(name, message_id):
        return until(lambda: request(urls[name], "/api/v2/mq/status?message_id=" + message_id).get("status") == "platform_queued",
                     message_id + " platform admission", timeout=60)

    def stored_envelope(message_id):
        with sqlite3.connect(folder / "data" / "mq.db") as db:
            row = db.execute("SELECT envelope,receipt FROM v2_messages WHERE id=?", (message_id,)).fetchone()
        assert row and row[0] and row[1], f"no atomically stored envelope and receipt for {message_id}"
        return json.loads(row[0]), json.loads(row[1])

    def stored_bytes(message_id):
        with sqlite3.connect(folder / "data" / "mq.db") as db:
            row = db.execute("SELECT envelope,receipt FROM v2_messages WHERE id=?", (message_id,)).fetchone()
        assert row and row[0] and row[1]
        return row

    def retry_original_envelope(raw):
        envelope = json.loads(raw)
        body = json.dumps({"recipient_urn": envelope["header"]["recipient_urn"],
                           "expiry_unix": envelope["header"]["expiry"],
                           "envelope": base64.b64encode(raw).decode()}).encode()
        auth = run_cli(helper, "sign-store", folder / "keys-a", body.hex())
        req = urllib.request.Request(urls["platform"] + "/api/v2/mq/store", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Ed25519 {auth['signature']}:{auth['pubkey']}"})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as response:
            return json.load(response)

    def legacy_store(message_id):
        v1 = run_cli(helper, "encrypt-envelope", folder / "keys-a", identities["b"]["urn"],
                     identities["b"]["x25519_pubkey"], b"legacy message".hex(), message_id)
        body = json.dumps({"recipient_urn": identities["b"]["urn"],
                           "expiry_unix": int(time.time()) + 300,
                           "payload_proto": base64.b64encode(bytes.fromhex(v1["envelope_proto_hex"])).decode()}).encode()
        auth = run_cli(helper, "sign-store", folder / "keys-a", body.hex())
        req = urllib.request.Request(urls["platform"] + "/api/v1/mq/store", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Ed25519 {auth['signature']}:{auth['pubkey']}"})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as response:
            return json.load(response)

    def legacy_store_rejected(current_policy):
        try:
            legacy_store("v1-bypass")
            raise AssertionError("platform accepted v1 Agent-to-Agent message under compliance policy")
        except urllib.error.HTTPError as error:
            assert error.code == 403, f"unexpected v1 rejection: {error.code}"
            notice = json.load(error)
            assert notice["error"] == "upgrade_required"
            if current_policy:
                assert notice["consent_required"] is True
                assert notice["policy_url"] == "/api/v2/policy"
                assert notice["policy_mode"] == "compliance" and notice["policy_epoch"] == 2
                assert notice["policy_hash"] == hashlib.sha256(policy_file.read_bytes()).hexdigest()
            else:
                assert notice["consent_required"] is None and "policy_url" not in notice
        with sqlite3.connect(folder / "data" / "mq.db") as db:
            assert db.execute("SELECT COUNT(*) FROM messages WHERE id='v1-bypass'").fetchone()[0] == 0

    checks = []
    try:
        configure("private", 1)
        start("platform")
        assert request(urls["platform"], "/api/v2/policy")["policy"]
        private_hint = request(urls["platform"], "/api/v1/bootstrap")["v2"]
        assert private_hint["policy_mode"] == "private" and not private_hint["upgrade_required"]
        start("a")
        start("b")
        registered("a")
        registered("b")
        for name in ("a", "b"):
            state = disclosure(name, "private", 1)
            assert state["policy_verified"] and state["platform_can_decrypt"] is False
            assert state["v2_send_ready"] and not state["local_compliance_authorized"]
            assert state["platform_id"] == platform_identity["peer_id"]

        try:
            request(urls["a"], "/api/v1/mq/store", {"message_id": "silent-legacy",
                    "recipient_urn": identities["b"]["urn"], "text": "must use v2"})
            raise AssertionError("new helper silently accepted v1 after a root pin")
        except urllib.error.HTTPError as error:
            assert error.code == 409 and json.load(error)["code"] == "upgrade_required"
        assert send("a", "v2-private", "b", "private body")["success"]
        private = receive("b", "v2-private")
        assert private["text"] == "private body" and private["mode"] == "private" and private["policy_epoch"] == 1
        envelope, receipt = stored_envelope("v2-private")
        assert envelope["slots"] == [] and envelope["header"]["mode"] == "private"
        assert receipt["result"] == "accepted-uninspected" and b"private body" not in json.dumps(envelope).encode()
        checks.append("Signed ephemeral private handshake and verified Agent delivery; no gateway slot")
        request(urls["b"], "/api/v1/mq/ack", {"message_ids": ["v2-private"]})

        stop("b")
        assert send("a", "v2-old-private", "b", "unread old private body")["success"]
        queued("a", "v2-old-private")
        stored_envelope("v2-old-private")
        assert legacy_store("v1-before-cutover")["ok"] is True
        old_envelope_raw, old_receipt_raw = stored_bytes("v2-old-private")
        stop("a")
        stop("platform")

        configure("compliance", 2)
        start("platform")
        compliance_hint = request(urls["platform"], "/api/v1/bootstrap")["v2"]
        assert compliance_hint["policy_mode"] == "compliance" and compliance_hint["consent_required"]
        repeated = retry_original_envelope(old_envelope_raw)
        assert repeated["ok"] is True and repeated["message_id"] == "v2-old-private"
        assert base64.b64decode(repeated["receipt"]) == old_receipt_raw
        start("a")
        start("b")
        registered("a")
        registered("b")
        for name in ("a", "b"):
            state = disclosure(name, "compliance", 2)
            assert state["policy_verified"] and state["platform_can_decrypt"] is True
            assert state["state"] == "consent_required" and not state["v2_send_ready"]
            assert state["gateway_key_id"] and not state["local_compliance_authorized"]
        compliance_hashes = {name: disclosure(name, "compliance", 2)["policy_hash"]
                             for name in ("a", "b")}
        assert all(item["message_id"] != "v2-old-private" for item in inbox("b"))
        assert all(item["message_id"] != "v1-before-cutover" for item in inbox("b"))
        def unauthorized_disclosure_rejected():
            try:
                request(urls["a"], "/api/v2/mq/store", {"message_id": "v2-without-owner-authorization",
                        "recipient_urn": identities["b"]["urn"], "text": "must remain private"})
            except urllib.error.HTTPError as error:
                assert error.code == 403, f"unexpected disclosure rejection: {error.code}"
                return True
            raise AssertionError("agent accepted compliance disclosure without local authorization")
        until(unauthorized_disclosure_rejected, "local compliance authorization gate")
        stop("a")
        stop("b")
        for name in ("a", "b"):
            run_cli(helper, "v2-allow-compliance", folder / f"keys-{name}",
                    compliance_hashes[name],
                    "Owner explicitly authorizes this isolated gateway-readable process test")
        start("a")
        start("b")
        registered("a")
        registered("b")
        for name in ("a", "b"):
            state = disclosure(name, "compliance", 2)
            assert state["state"] == "ready" and state["v2_send_ready"]
            assert state["local_compliance_authorized"] is True
        legacy_store_rejected(True)
        assert send("a", "v2-compliance", "b", "gateway-readable body")["success"]
        admitted = receive("b", "v2-compliance")
        assert admitted["text"] == "gateway-readable body" and admitted["mode"] == "compliance" and admitted["policy_epoch"] == 2
        envelope, receipt = stored_envelope("v2-compliance")
        assert [slot["role"] for slot in envelope["slots"]] == ["recipient", "gateway"]
        assert receipt["result"] == "decrypted-admitted" and receipt["proof"]
        assert b"gateway-readable body" not in json.dumps(envelope).encode()
        checks.append("Policy epoch cutover quarantines unread private ciphertext")
        checks.append("A lost response can retrieve the byte-identical old receipt after policy cutover")
        checks.append("Compliance disclosure fails closed until each Agent explicitly authorizes it locally")
        checks.append("Agents report verified decryptability and reject silent legacy sends during migration")
        checks.append("Compliance policy rejects signed v1 Agent-to-Agent bypass at the platform")
        checks.append("Staged private policy permits old v1, then signed upgrade hint and cutover isolate it")
        checks.append("Gateway decrypts and signs exact compliance envelope; recipient verifies receipt proof")

        run_cli(helper, "v2-disallow-compliance", folder / "keys-a",
                "Owner withdraws permission for future gateway-readable messages")
        withdrawn = disclosure("a", "compliance", 2)
        assert withdrawn["state"] == "consent_required" and not withdrawn["local_compliance_authorized"]
        try:
            request(urls["a"], "/api/v2/mq/store", {"message_id": "after-withdrawal",
                    "recipient_urn": identities["b"]["urn"], "text": "not disclosed"})
            raise AssertionError("running helper sent compliance data after local withdrawal")
        except urllib.error.HTTPError as error:
            assert error.code == 403 and json.load(error)["code"] == "consent_required"
        checks.append("Owner can withdraw exact-policy disclosure permission without replacing identity")

        stop("platform")
        original_config = config.read_text(encoding="utf-8")
        assert "v2:\n  enabled: true" in original_config
        config.write_text(original_config.replace("v2:\n  enabled: true", "v2:\n  enabled: false", 1), encoding="utf-8")
        start("platform")
        legacy_store_rejected(False)
        checks.append("Removing v2 service configuration after cutover cannot reopen legacy v1")

        result = {"result": "PASS", "checks": checks, "logs": str(folder),
                  "scope": "Real isolated local Platform and two helper processes; no Web, Hermes, or production deployment"}
        (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        for name in list(processes):
            stop(name)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
