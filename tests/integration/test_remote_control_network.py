"""Real local Go platform/helpers + Python remote authority. No public messages."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
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
    folder = ROOT / "build" / "integration" / "remote-control-network" / str(uuid.uuid4())
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
    bridge = store = peer_store = None
    # The production platform accepts environment overrides even with -config.
    # Keep this test's process paths/listeners in its fresh local sandbox.
    process_env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLATFORM_")}

    def start(name):
        log = (folder / f"{name}.log").open("ab")
        logs.append(log)
        command = [str(args.platform.resolve()), "-config", str(config)] if name == "platform" else [
            str(args.helper.resolve()), "daemon", str(folder / f"keys-{name}"), urls["platform"], str(ports[name])]
        processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=process_env, cwd=folder,
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
        foreign_owner = "another-local-owner|native-session"
        foreign_contact = store.prepare_contact("foreign-contact", ["其他账号的联系人"], console["urn"], foreign_owner)
        foreign_lease = store.begin_confirmation(foreign_contact["approval_id"], foreign_owner)
        store.finish_confirmation(foreign_contact["approval_id"], foreign_lease["token"], foreign_owner, "同意")
        bridge = RemoteBridge(folder / "remote.sqlite3", store, agent["urn"])
        bridge.pair(console["urn"], "network-test-owner", ["capabilities", "contacts.list"], iso(3600))

        def send_request(method, params=None, packet_overrides=None, envelope_overrides=None):
            rid = str(uuid.uuid4())
            packet = {"protocol": PROTOCOL, "type": "request", "request_id": rid, "method": method,
                      "params": params or {}, "agent_urn": agent["urn"], "console_urn": console["urn"], "deadline": iso(120)}
            packet.update(packet_overrides or {})
            body = {"message_id": rid, "recipient_urn": agent["urn"], "text": json.dumps(packet),
                    "kind": "control.request", "conversation_id": "control:" + rid, "deadline": packet["deadline"]}
            body.update(envelope_overrides or {})
            assert outgoing.store(body)["success"]
            message = until(lambda: next((m for m in incoming.retrieve() if m["message_id"] == rid), None), "control arrival")
            assert message["sender_urn"] == console["urn"]
            # Native inbox must not ACK or ingest control messages before the bridge.
            store.sync_inbox(incoming)
            assert any(m["message_id"] == rid for m in incoming.retrieve())
            return packet, message

        def roundtrip(method, restart=False, params=None, fail_delivery=False):
            nonlocal bridge
            packet, message = send_request(method, params)
            rid = packet["request_id"]
            first_response = bridge.handle(message)
            if restart:
                bridge.close()
                bridge = RemoteBridge(folder / "remote.sqlite3", store, agent["urn"])
                assert bridge.handle(message) == first_response
            if fail_delivery:
                class UnavailableResponseTransport:
                    def store(self, body):
                        raise OSError("isolated test: helper response store unavailable")

                    def ack(self, message_ids):
                        raise AssertionError("Request ACK happened before response was accepted")

                try:
                    bridge.process(message, UnavailableResponseTransport())
                except OSError:
                    pass
                else:
                    raise AssertionError("Injected response store failure did not propagate")
                assert any(m["message_id"] == rid for m in incoming.retrieve())
                assert not any(m.get("in_reply_to") == rid for m in outgoing.retrieve())
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
        assert [c["aliases"] for c in contacts["result"]["contacts"]] == [["本机保存的联系人"]]
        assert roundtrip("contacts.list", fail_delivery=True)["result"] == contacts["result"]
        assert roundtrip("contacts.list", params={"unexpected": True})["error"]["code"] == "invalid_params"
        assert roundtrip("inbox.list")["error"]["code"] == "method_not_allowed"
        assert roundtrip("attention.list")["error"]["code"] == "method_not_allowed"
        bridge.pair(console["urn"], "network-test-owner", ["capabilities", "contacts.list", "attention.list", "collaboration.state"], iso(3600))
        # A single owner cannot add the confirmed Console identity again under
        # a new contact ID. Use distinct unresolved identities for approval tests.
        pending_urn = f"urn:agent-comm:agent:{uuid.uuid4().hex}"
        pending = store.prepare_contact("pending-contact", ["需要主人核对"], pending_urn, owner)
        attention = roundtrip("attention.list", params={"after": 0, "limit": 100})["result"]
        notice = next(item for item in attention["items"] if item.get("approval_id") == pending["approval_id"])
        assert notice["state"] == "open" and "question" not in notice and "token" not in notice
        assert roundtrip("attention.list", params={"owner": foreign_owner})["error"]["code"] == "invalid_params"
        lease = store.begin_confirmation(pending["approval_id"], owner)
        store.finish_confirmation(pending["approval_id"], lease["token"], owner, "拒绝")
        updated = roundtrip("attention.list", params={"after": attention["cursor"]})["result"]
        assert next(item for item in updated["items"] if item["attention_id"] == notice["attention_id"])["state"] == "resolved"

        # Independent owners, independent local task IDs, real encrypted wire.
        peer_store = Store(folder / "peer-collaboration.sqlite3", local_urn=console["urn"])
        peer_owner = "network-peer-owner|native-session"

        def native_confirm(database, prepared, principal):
            if prepared.get("decision") == "ask":
                lease = database.begin_confirmation(prepared["approval_id"], principal)
                assert database.finish_confirmation(prepared["approval_id"], lease["token"], principal, "同意")["decision"] == "allow"

        native_confirm(peer_store, peer_store.prepare_contact("agent-a", ["测试对象"], agent["urn"], peer_owner), peer_owner)
        scope = {"purpose": "本机隔离双边约定测试", "topic": "协议验收",
                 "capabilities": ["propose_meeting", "accept_meeting"], "recipient_ids": ["test-contact"],
                 "participant_ids": ["self", "test-contact"], "resource_ids": [],
                 "window_start": iso(3600), "window_end": iso(172800), "max_duration_minutes": 30,
                 "max_candidates": 2, "max_actions": 20, "expires_at": iso(172800)}
        native_confirm(store, store.prepare_task("local-a", scope, owner), owner)
        peer_scope = {**scope, "recipient_ids": ["agent-a"], "participant_ids": ["self", "agent-a"]}
        native_confirm(peer_store, peer_store.prepare_task("local-b", peer_scope, peer_owner), peer_owner)
        event_number = 0

        def send_event(database, kind, payload=None):
            nonlocal event_number
            event_number += 1
            principal, task, transport = (owner, "local-a", incoming) if database is store else (peer_owner, "local-b", outgoing)
            result = database.prepare_collaboration(task, "network-shared", "network-op-" + str(event_number), kind, payload or {}, principal)
            native_confirm(database, result, principal)
            assert database.dispatch(result["operation_id"], principal, transport)["status"] == "accepted"

        def receive(database, transport):
            messages = [m for m in transport.retrieve() if m.get("task_id") == "network-shared"]
            for message in messages:
                database.ingest_message(message)
            if messages:
                transport.ack([m["message_id"] for m in messages])
            return messages

        def advance():
            for database, principal, transport in ((store, owner, incoming), (peer_store, peer_owner, outgoing)):
                receive(database, transport)
                for operation in database.collaborations(principal)["operations"]:
                    if operation["status"] in {"ready", "sending"} and operation["decision"] == "allow":
                        assert database.dispatch(operation["operation_id"], principal, transport)["status"] == "accepted"
            return store.collaborations(owner)["collaborations"], peer_store.collaborations(peer_owner)["collaborations"]

        send_event(store, "invite", {"peer_id": "test-contact"})
        invitation = until(lambda: receive(peer_store, outgoing), "bilateral invitation")[0]
        assert any(item["kind"] == "new_collaboration_request" and item["state"] == "open" for item in peer_store.attention(peer_owner)["items"])
        send_event(peer_store, "join", {"message_id": invitation["message_id"]})
        until(lambda: (advance()[0][0].get("joined")), "independent task join")
        start_time = datetime.now(timezone.utc) + timedelta(hours=2)
        terms = {"proposal_id": "online-meeting", "version": 1, "topic": scope["topic"],
                 "participant_ids": ["self", "test-contact"], "start": start_time.isoformat(),
                 "end": (start_time + timedelta(minutes=30)).isoformat()}
        send_event(store, "proposal", terms)
        until(lambda: advance()[1][0].get("terms"), "shared proposal")
        assert peer_store.inbox(peer_owner, "local-b")["messages"]
        send_event(store, "accept")
        send_event(peer_store, "accept")

        def both_closed():
            left, right = advance()
            return left[0]["phase"] == right[0]["phase"] == "closed"

        until(both_closed, "matching bilateral agreement", timeout=35)
        left, right = advance()
        assert left[0]["agreement"] == right[0]["agreement"]
        assert left[0]["task_id"] == "local-a" and right[0]["task_id"] == "local-b"
        snapshot = roundtrip("collaboration.state", params={"task_id": "local-a"})["result"]
        assert snapshot["collaboration"]["calendar_created"] is False
        assert snapshot["collaboration"]["collaborations"][0]["phase"] == "closed"
        final_attention = roundtrip("attention.list")["result"]
        assert any(item["kind"] == "collaboration_completed" for item in final_attention["items"])

        # These packets still traverse signed/encrypted Go transport. The bridge
        # must compare payload claims against the authenticated outer envelope.
        for packet_overrides, envelope_overrides in (
            ({"console_urn": agent["urn"]}, {}),
            ({"request_id": "forged-inner-request-id"}, {}),
            ({}, {"conversation_id": "control:wrong-correlation"}),
        ):
            _, malformed = send_request("contacts.list", packet_overrides=packet_overrides,
                                        envelope_overrides=envelope_overrides)
            try:
                bridge.process(malformed, incoming)
            except ValueError:
                pass
            else:
                raise AssertionError("Untrusted control identity/correlation was accepted")
            assert any(m["message_id"] == malformed["message_id"] for m in incoming.retrieve())
            assert not any(m.get("in_reply_to") == malformed["message_id"] for m in outgoing.retrieve())
            incoming.ack([malformed["message_id"]])  # Remove only this test's known poison packet.

        # Approval responses are supported only through an explicitly scoped
        # local pairing, and that grant never extends to another owner's work.
        remote_approval_urn = f"urn:agent-comm:agent:{uuid.uuid4().hex}"
        remote_pending = store.prepare_contact("remote-approved", ["远程明确确认的联系人"], remote_approval_urn, owner)
        native_lease = store.begin_confirmation(remote_pending["approval_id"], owner)
        approval_params = {"approval_id": remote_pending["approval_id"], "decision": "approve"}
        own_before = store.state(owner)
        assert roundtrip("approval.respond", params=approval_params)["error"]["code"] == "method_not_allowed"
        assert store.state(owner) == own_before
        foreign_pending_urn = f"urn:agent-comm:agent:{uuid.uuid4().hex}"
        foreign_pending = store.prepare_contact("foreign-pending", ["其他账号待确认的联系人"], foreign_pending_urn, foreign_owner)
        foreign_before = store.state(foreign_owner)
        bridge.pair(console["urn"], "network-test-owner", ["capabilities", "contacts.list", "conversation.send",
                    "conversation.get", "approval.respond", "test.unimplemented"], iso(3600))
        methods = {item["name"]: item["available"] for item in roundtrip("capabilities")["result"]["methods"]}
        assert methods["approval.respond"] is True
        assert roundtrip("test.unimplemented")["error"]["code"] == "unsupported_method"
        assert roundtrip("approval.respond")["error"]["code"] == "invalid_params"
        assert roundtrip("approval.respond", params={**approval_params, "owner_session": foreign_owner})["error"]["code"] == "invalid_params"
        assert roundtrip("approval.respond", params={"approval_id": foreign_pending["approval_id"],
                         "decision": "approve"})["error"]["code"] == "invalid_params"
        assert store.state(foreign_owner) == foreign_before
        assert store.state(owner) == own_before
        approved = roundtrip("approval.respond", params=approval_params, restart=True, fail_delivery=True)
        assert approved["result"] == {"approval_id": remote_pending["approval_id"], "decision": "allow", "status": "approved_once"}
        assert any(contact["contact_id"] == "remote-approved" for contact in roundtrip("contacts.list")["result"]["contacts"])
        try:
            store.finish_confirmation(remote_pending["approval_id"], native_lease["token"], owner, "拒绝")
        except ValueError:
            pass
        else:
            raise AssertionError("A stale native lease reversed the explicit remote decision")
        assert roundtrip("approval.respond", params={**approval_params, "decision": "deny"})["error"]["code"] == "invalid_params"
        decision = next(item for item in store.state(owner)["approval_decisions"] if item["approval_id"] == remote_pending["approval_id"])
        assert decision["status"] == "approved"
        assert store.state(foreign_owner) == foreign_before
        bridge.conversations = True
        submitted = roundtrip("conversation.send", params={"text": "隔离测试：只排队，不调用模型"})
        assert submitted["result"]["status"] == "submitted"
        conversation = roundtrip("conversation.get", params={"conversation_id": submitted["result"]["conversation_id"]})
        assert len(conversation["result"]["turns"]) == 1
        turn = conversation["result"]["turns"][0]
        assert turn["status"] == "submitted" and turn["response"] is None and turn["error"] is None

        bridge.revoke(console["urn"])
        assert roundtrip("contacts.list")["error"]["code"] == "not_paired"
        assert roundtrip("approval.respond", params=approval_params)["error"]["code"] == "not_paired"
        report = {"result": "PASS", "checks": ["real signed encrypted control roundtrip", "agent-owned contacts",
            "native inbox leaves control requests unacknowledged", "bridge restart preserves immutable response",
            "method scope enforced", "local revocation enforced", "local owner contact isolation",
            "response store failure leaves request pending for idempotent retry", "invalid method parameters rejected",
            "authenticated sender claim and envelope correlation enforced", "unknown methods remain unsupported",
            "remote approval requires explicit scope and cannot cross owner boundaries",
            "explicit remote decision survives restart and delivery retry, invalidates native lease, and cannot be reversed",
            "conversation submission remains queued without a model response",
            "attention explicit pairing, owner isolation, and native resolution tombstones",
            "independent local tasks negotiate over real authenticated encrypted helper messages",
            "matching agreement and completion attention visible through read-only RPC"], "logs": str(folder),
            "scope": "Fresh local identities and real Go processes; no production messages or model calls"}
        (folder / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if bridge:
            bridge.close()
        if store:
            store.close()
        if peer_store:
            peer_store.close()
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
