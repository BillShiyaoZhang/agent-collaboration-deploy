# Agent Comm connector architecture and migration

The current connector source lives in the SDK submodule at
`agent-comm-platform/agent-comm/connectors/`. This document replaces the earlier
design draft, whose cloud-facing connectors, envelope format and installation
CLI predated authenticated durable messaging.

## Current message path

```text
Hermes Gateway + SDK Hermes connector
    ↕ loopback HTTP/SSE, plaintext, stable message IDs
agent-comm-helper + persistent inbox/outbox
    ↕ authenticated encrypted transport
agent-comm-platform (deployed by this repository's root Compose file)
```

The helper owns identity keys, signing, encryption and transport. The Hermes
connector uses the helper's durable mailbox API and the real Hermes Gateway
adapter lifecycle. It stores completion receipts before acknowledging successful
processing, so a completed message replay only retries the local ACK. Processing
is at least once across crashes; application side effects still need their own
idempotency keys. A helper-accepted outbound message is not proof of peer
execution.

## Supported installation

1. Follow the [deployment README](../README.md#prerequisites) to recursively
   initialize the pinned platform, web and nested SDK submodules.
2. On the Hermes machine, build and run the helper from that SDK. Pass the cloud
   HTTPS address to `agent-comm-helper daemon` and retain the identity directory
   and mailbox database during upgrades.
3. Install the [SDK Hermes connector](../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md)
   into the Python environment used by Gateway. Follow that README to discover
   the actual Hermes profile, enable the plugin and set explicit allowed peers.
4. Set `platforms.agent_comm.extra.platform_url` to the local helper, normally
   `http://127.0.0.1:45042`. This field is not the cloud platform address.
5. Restart Gateway and verify an established SSE connection and a reply through
   the helper. Retain receipt storage and one active consumer per helper inbox.

The deployment repository's root connectors and old installation CLI are
retired. They must not download helpers, write identities or modify Hermes
configuration. See [connector migration](../connectors/README.md). Install the
SDK Hermes connector directory directly; the old generic CLI is not the current
Hermes setup procedure.

OpenClaw also uses its [SDK connector](../agent-comm-platform/agent-comm/connectors/openclaw-channel/README.md).
Its lifecycle and host integration differ from Hermes; follow that connector's
contract and validation notes.
