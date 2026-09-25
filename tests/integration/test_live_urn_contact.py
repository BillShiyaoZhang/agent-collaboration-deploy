"""Opt-in production smoke test with two disposable synthetic Agent identities.

The script creates local keys and Store databases in a temporary directory,
uses the specified HTTPS Platform, and removes those local identities on exit.
It never uses or modifies an existing Hermes profile. The remote Registry may
retain the disposable public registrations until their normal expiry.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / "agent-comm-platform" / "agent-comm"
sys.path[:0] = [str(SDK / "python"), str(SDK / "tools")]
from agent_comm_runtime.store import Store  # noqa: E402
from agent_comm_runtime.transport import HelperTransport  # noqa: E402
from test_helper_platform import port, request, until  # noqa: E402


def helper_cli(executable, *args):
    result = subprocess.run([str(executable), *map(str, args)], check=True,
                            capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()


def local_action(store, method, params, owner):
    action_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    return store.remote_mutation(method, params, owner, request_key=action_id,
                                 fingerprint=action_id, valid_until=time.time() + 180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", required=True, type=Path)
    parser.add_argument("--platform-url", required=True)
    parser.add_argument("--trust-file", required=True, type=Path)
    parser.add_argument("--expected-policy-hash", required=True)
    args = parser.parse_args()
    helper = args.helper.resolve(strict=True)
    trust = json.loads(args.trust_file.read_text(encoding="utf-8"))
    platform_url = args.platform_url.rstrip("/")
    parsed = urllib.parse.urlsplit(platform_url)
    if parsed.scheme != "https" or platform_url != trust["platform_origin"]:
        raise ValueError("Live test requires the trusted HTTPS Platform origin")
    expected_hash = args.expected_policy_hash.lower()
    if len(expected_hash) != 64 or any(c not in "0123456789abcdef" for c in expected_hash):
        raise ValueError("Expected policy hash must be 64 hex characters")
    policy_response = request(platform_url, "/api/v2/policy")
    policy_bytes = base64.b64decode(policy_response["policy"], validate=True)
    policy = json.loads(policy_bytes)
    actual_hash = hashlib.sha256(policy_bytes).hexdigest()
    if (actual_hash != expected_hash or policy["platform_id"] != trust["platform_peer_id"]
            or policy["mode"] != "compliance" or policy["allow_v1"] is not False):
        raise ValueError("Live signed-policy identity or disclosure mode differs from the test expectation")

    checks = []
    processes, logs, stores = {}, [], []
    scratch = ROOT / "build" / "integration" / "live-urn-contact"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="synthetic-", dir=scratch) as temporary:
        folder = Path(temporary)
        ports = {name: port() for name in ("a", "b")}
        urls = {name: f"http://127.0.0.1:{number}" for name, number in ports.items()}
        keys = {name: folder / f"keys-{name}" for name in ("a", "b")}
        identities = {name: helper_cli(helper, "init", keys[name]) for name in keys}
        for name in keys:
            helper_cli(helper, "v2-pin-policy-root", keys[name], trust["policy_root_public_key_hex"],
                       trust["platform_peer_id"], "Previously verified public v0.9.1 release trust anchor")

        def start(name):
            log = (folder / f"helper-{name}.log").open("ab")
            logs.append(log)
            processes[name] = subprocess.Popen(
                [str(helper), "daemon", str(keys[name]), platform_url, str(ports[name])],
                cwd=folder, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            return until(lambda: request(urls[name], "/info"), name + " helper startup", timeout=45)

        def stop(name):
            proc = processes.pop(name, None)
            if proc is not None:
                proc.terminate()
                proc.wait(timeout=15)

        try:
            for name in keys:
                start(name)
                state = until(lambda: (lambda value: value if value["policy_verified"] else None)(
                              request(urls[name], "/api/v2/disclosure")),
                              name + " disclosure", timeout=45)
                assert state["policy_verified"] is True and state["policy_hash"] == expected_hash
                assert state["v2_send_ready"] is False and state["local_compliance_authorized"] is False
            checks.append("Fresh synthetic agents do not inherit compliance disclosure authorization")

            for name in keys:
                stop(name)
                helper_cli(helper, "v2-allow-compliance", keys[name], expected_hash,
                           "Synthetic end-to-end test only; no real user's identity or content")
                start(name)
                until(lambda: request(urls[name], "/api/v2/disclosure").get("v2_send_ready"),
                      name + " explicit synthetic disclosure readiness", timeout=45)
                registration = until(lambda: request(urls[name], "/api/v1/platform/register", {}),
                                     name + " Platform registration", timeout=60)
                assert registration["registered"] is True
                until(lambda: request(platform_url, "/api/v1/registry/resolve?urn=" +
                                      urllib.parse.quote(identities[name]["urn"], safe="")).get("found"),
                      name + " Registry registration", timeout=60)
            checks.append("Explicit consent to the unchanged signed policy enables each synthetic helper")

            assert not any(list((keys[name] / "v2_peers").glob("*.json")) for name in keys)
            a = Store(folder / "a.sqlite3", local_urn=identities["a"]["urn"], owner_principal="synthetic-a")
            b = Store(folder / "b.sqlite3", local_urn=identities["b"]["urn"], owner_principal="synthetic-b")
            stores.extend((a, b))
            ta, tb = HelperTransport(urls["a"]), HelperTransport(urls["b"])
            owner_a, owner_b = "synthetic-a|test", "synthetic-b|test"

            first = local_action(a, "contacts.add", {"contact_id": "b", "aliases": ["B"],
                                                      "urn": identities["b"]["urn"]}, owner_a)
            assert first["status"] == "requested"
            assert a.state(owner_a)["contacts"][0]["connection_status"] == "pending"
            try:
                local_action(a, "messages.send", {"recipient_urn": identities["b"]["urn"],
                                                  "text": "before-acceptance"}, owner_a)
                raise AssertionError("Runtime allowed ordinary business mail before friendship acceptance")
            except ValueError:
                pass
            a.flush_social_outbox(ta)
            incoming = until(lambda: (b.sync_inbox(tb), next((r for r in b.contact_requests(owner_b)["contact_requests"]
                                      if r["direction"] == "incoming" and r["status"] == "pending"), None))[1],
                             "first URN-only friend request", timeout=120)
            assert incoming["peer_urn"] == identities["a"]["urn"]
            for name, peer in (("a", "b"), ("b", "a")):
                pins = list((keys[name] / "v2_peers").glob("*.json"))
                assert len(pins) == 1
                pin = json.loads(pins[0].read_text(encoding="utf-8"))
                assert pin["urn"] == identities[peer]["urn"] and pin["source"] == "registry"
                assert not pin.get("verification_note")
            checks.append("First request reached B using only URNs and authenticated Registry-discovered keys")

            local_action(b, "contacts.respond", {"request_id": incoming["request_id"],
                                                 "decision": "reject"}, owner_b)
            b.flush_social_outbox(tb)
            until(lambda: (a.sync_inbox(ta), a.state(owner_a)["contacts"][0]["connection_status"] == "rejected")[1],
                  "rejection response", timeout=120)
            assert b.state(owner_b)["contacts"] == []
            early_id = "synthetic-early-" + uuid.uuid4().hex
            assert ta.store({"message_id": early_id, "recipient_urn": identities["b"]["urn"],
                             "kind": "chat.message", "text": "quarantined-test-body"})["success"]
            until(lambda: (b.sync_inbox(tb), b._get("inbound", early_id))[1],
                  "direct helper business mail", timeout=120)
            assert b._get("inbound", early_id)["quarantined"] is True
            assert all(m["message_id"] != early_id for m in b.inbox(owner_b)["messages"])
            checks.append("B rejected A; direct helper business mail remained quarantined")

            retry = local_action(a, "contacts.add", {"contact_id": "b", "aliases": ["B"],
                                                       "urn": identities["b"]["urn"]}, owner_a)
            assert retry["status"] == "requested"
            a.flush_social_outbox(ta)
            second = until(lambda: (b.sync_inbox(tb), next((r for r in b.contact_requests(owner_b)["contact_requests"]
                                    if r["status"] == "pending"), None))[1],
                           "second URN-only friend request", timeout=120)
            assert second["request_id"] != incoming["request_id"]
            local_action(b, "contacts.respond", {"request_id": second["request_id"],
                                                 "decision": "accept"}, owner_b)
            assert b.state(owner_b)["contacts"][0]["connection_status"] == "connected"
            reply = local_action(b, "messages.send", {"recipient_urn": identities["a"]["urn"],
                                                      "text": "accepted-reply"}, owner_b)
            b.flush_social_outbox(tb)
            awaiting = until(lambda: (lambda msgs: msgs if any(m["kind"] == "contact.response" and
                                m.get("conversation_id") == second["request_id"] for m in msgs) and
                                any(m["message_id"] == reply["message_id"] for m in msgs) else None)(ta.retrieve()),
                             "acceptance and reordered business mail", timeout=120)
            response = next(m for m in awaiting if m["kind"] == "contact.response" and
                            m.get("conversation_id") == second["request_id"])
            chat = next(m for m in awaiting if m["message_id"] == reply["message_id"])
            assert a.ingest_message(chat)["status"] == "quarantined"
            a.ingest_message(response)
            ta.ack([response["message_id"], chat["message_id"]])
            assert a.state(owner_a)["contacts"][0]["connection_status"] == "connected"
            assert any(m["message_id"] == chat["message_id"] for m in a.inbox(owner_a)["messages"])
            assert b._get("inbound", early_id)["quarantined"] is True
            checks.append("Acceptance connected both address books; reordered mail was released, rejected old mail was not")

            sent = local_action(a, "messages.send", {"recipient_urn": identities["b"]["urn"],
                                                     "text": "synthetic-after-accept"}, owner_a)
            a.flush_social_outbox(ta)
            until(lambda: (b.sync_inbox(tb), next((m for m in b.inbox(owner_b)["messages"]
                          if m["message_id"] == sent["message_id"]), None))[1],
                  "accepted business delivery", timeout=120)
            assert b.mark_read(sent["message_id"], owner_b)["message"]["read"] is True
            assert a.mark_read(reply["message_id"], owner_a)["message"]["read"] is True
            assert not any(c.get("trusted") for c in a.state(owner_a)["contacts"] + b.state(owner_b)["contacts"])
            assert a.state(owner_a)["tasks"] == [] and b.state(owner_b)["tasks"] == []
            checks.append("Both directions delivered and read; friendship granted no task or trusted status")
        except BaseException:
            for name in keys:
                log_path = folder / f"helper-{name}.log"
                if log_path.exists():
                    print(f"Helper {name} log:\n{log_path.read_text(encoding='utf-8', errors='replace')[-12000:]}",
                          file=sys.stderr)
            raise
        finally:
            for store in stores:
                store.close()
            for name in tuple(processes):
                stop(name)
            for log in logs:
                log.close()

    print(json.dumps({"status": "passed", "platform": platform_url,
                      "policy_epoch": policy["epoch"], "checks": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
