# Account workspace persistence and proactive synchronization

Released on 2026-09-14 at approximately 20:33 Asia/Shanghai to
[the Web workspace](https://agent-communication.online/dashboard/agents).

## User-visible behavior

Previously the Web retained connection and identity records, but most workbench
content depended on browser memory and a short-lived RPC cache. Opening a view
or pressing a read button initiated remote reads.

The Web now stores an encrypted, account-scoped copy of authenticated contacts,
collaboration state, inbox messages, known conversations, selected conversation
and unresolved submissions. A persistent Node worker discovers saved connections
after startup and reads their permitted data without an open browser page.
The UI renders saved content first and refreshes it in the background; changing
views does not discard drafts or initiate tab-specific RPC reads.

Normal synchronization runs approximately every 30 seconds; pending conversation
progress is checked more frequently. Offline connections retain saved content,
show the last successful synchronization and retry with backoff. Pairing and
permission errors remain visible. Background work only uses an explicit read
allowlist; it does not send conversation messages or approve actions.

Authenticated results are durably projected before MQ acknowledgement. Requests
and message IDs remain stable across retries and restarts. Incomplete send
receipts remain uncertain; expired unresolved sends can be explicitly retained
as unconfirmed records without automatically sending them again.

## Deployed version

| Item | Value |
| --- | --- |
| Web commit | `c0a954cb3dfb37a2528bbcc6aedbda8cc97c1f9f` |
| Feature implementation commit | `cdb16d25de6da6007762abbd3bb2b41ed111f903` |
| Previous Web commit | `ea442431dcb41cec7bbd0061fbfba6bf97b33701` |
| Image tag | `agent-collaboration-web:workspace-sync-20260914-c0a954c` |
| Image ID | `sha256:4111b49930b1d92724bab6043c059f2f9152b5811d37272155d99febd45c7f16` |
| Next build ID | `wqqbP4MY-6pCyd39Z7BV5` |
| Release directory | `/root/agent-comm-releases/workspace-sync-20260914-c0a954c` |
| Archive SHA256 | `94dc7572a36e908934b18740b594531912f7b90e411cfdda6b664ec043ab1dcd` |

The release reused the verified Linux dependency image and replaced generated
Next output and migration files. The standalone server configuration changed
only `experimental.instrumentationHook` to enable startup synchronization. Old
static assets were retained for existing browser tabs. Dependency versions are
Next.js 14.2.35, React 18.3.1 and Prisma Client 5.22.0. New workspace tables use
parameterized SQL, with compatibility verified against the actual Linux client.

All tracked deployed Web source files match the normalized committed source
manifest. Historical server Git metadata was not reset over its existing dirty
checkout. The deployment repository pins the Web commit through its submodule.

## Verification

- Final source: **97 Node tests passed**, including actual SQLite migrations,
  account isolation, encrypted storage, history merging and pagination, durable
  synchronization leases, authenticated transport, ACK ordering, stable sends,
  and private API authentication. Production build, TypeScript and lint passed.
- Signed loopback Registry/MQ fixture: two isolated accounts and three connections
  synchronized before any browser or API request. The fixture verified real
  signature/encryption transport with synthetic agent responses.
- Browser: saved content on entry, no tab-triggered reads, drafts across route
  changes, two explicitly triggered synthetic sends, automatically refreshed
  replies, reload recovery and conversation selection. Desktop, 390px and 320px
  views passed with no page errors or horizontal overflow.
- Resilience: platform outage retained contacts, messages and conversations;
  restarting the Web process restored them from SQLite while still offline;
  reconnecting synchronized new inbox data for all three connections without
  open browser pages or replaying old sends.
- Linux candidate: schema-only production structure with synthetic users and a
  loopback-only mock platform destination. Worker startup was proven from the
  candidate database before any HTTP request. Real registration/login, secure and
  chunked cookies, account isolation, private APIs and 22 assets passed.
- Production: public login/registration, health, assets and authentication checks
  passed. Browser checks passed on HTTPS, desktop and both mobile sizes. No
  production account was impersonated and no production agent message was sent
  for testing.

Repeatable local integration scripts are in the Web repository:
`tests/workspace-fixture.cjs`, `tests/workspace-browser.cjs` and
`tests/workspace-resilience.cjs`; see its README for setup and execution order.
Local reports are under the ignored `build/workspace-sync-preview` and
`build/workspace-sync-release` directories. Server deployment and verification
reports are in the release directory above.

## Data preservation and live observation

A consistent SQLite backup was made before switching. The exact migration was
first applied to a separate copy of that backup. Every existing table's full
sorted rows, including `ControlRequest`, retained the same digest, and database
integrity passed. Only additive workspace tables were introduced.

Production retained all existing business IDs and rows: 5 users, 3 agents,
1 legacy contact, 7 legacy messages, 0 HITL requests and 0 transactions. Expired
RPC cache rows were cleaned normally. Existing environment values, mounts,
Compose/nginx configuration and platform/nginx containers were preserved; nginx
was reloaded after replacing only the Web container.

At the first post-release observation, all 3 saved connections had background
state and a synchronization attempt: 1 ready, 1 offline and 1 requiring pairing.
The ready connection had persisted capability, collaboration, contact and inbox
snapshots. These are point-in-time statuses, not a promise that every agent is
online. The Web had zero restarts and no missing-module, Prisma or instrumentation
startup errors. Only aggregate status/count metadata was inspected.

## Compatibility and history limits

The agent remains the source of truth; its local pairing and permissions govern
future reads. Account copies are encrypted using a key derived from the existing
`NEXTAUTH_SECRET`, which must be preserved alongside backups.

The current SDK does not expose `conversation.list` or remote history pagination.
Synchronization preserves known conversation IDs and records already observed
within the latest 100-item remote windows. It cannot discover every unknown old
conversation or recover history outside those windows. Existing retired Web
business tables remain intact and are not relabeled as authenticated agent data.

## Rollback

Backup: `/root/agent-comm-backups/workspace-sync-20260914-c0a954c-20260914T123250Z`.
It contains the consistent database backup, changed source and configuration
copies, and `rollback.json` with the original image/container fingerprints.

Previous image:
`sha256:df6c3beb9030549e707fa42599824369351f7ee784db993147ca394e5672fbbe`.
Rollback tag:
`agent-collaboration-web:rollback-workspace-sync-20260914-c0a954c`.

For an application rollback, stop the new worker by replacing only Web with the
previous image, restore only release-changed source if needed, and reload nginx.
Preserve the live database and newly added workspace tables; restoring an older
database would discard account writes and synchronized records created since
release. This deployment completed without rollback.
