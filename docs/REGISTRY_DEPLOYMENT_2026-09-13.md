# Registry ownership deployment — 2026-09-13

Status: deployed and verified on the public HTTPS and TCP libp2p endpoints.
The user explicitly approved Workbench's Alibaba Cloud OSS transfer intermediary.
Only the platform container was replaced; the switch and initial verification
completed in 1.05 seconds.

## Production result

- Image: `sha256:4c3ab94f2a4b9b6594b2d7d717ecd9b1cae3f04ed5594703c70a465eb3e3d51b`.
- Image tag: `agent-platform:registry-ownership-20260913-c93fa234`.
- Actual running binary matches the SHA-256 below.
- Owner HTTP registration returned 200. Both wrong-owner overwrite and first
  registration returned 400. The original record and TTL were unchanged, and
  `PrepareMessage` succeeded before and after the rejected overwrite.
- Public TCP libp2p owner registration, update and authenticated resolution
  passed. Wrong-owner overwrite and first claim were explicitly rejected with
  `identity public key does not match urn`; original content and TTL were unchanged.
- The smoke test sent no messages and created two records. Only those exact test
  records were removed afterward. All two pre-existing user registry rows and all
  six pre-existing MQ rows matched the consistent backup byte for byte at the row
  level. The platform's own record was renewed with its owner signature.
- All four identity file hashes, original mounts and production configuration
  hashes matched. Web and nginx retained their original container IDs. All three
  services were running with zero restarts after verification.
- Public `/healthz`, `/api/v1/bootstrap`, `/` and `/login` returned 200.

Machine-readable evidence is saved locally in
`build/registry-ownership-release/production-smoke.json` and `release.json`, and on
the server in the release directory listed below.

## Verified target

- ECS instance: `i-0jleb7de83gsnoa0yuc2`.
- Public address: `8.130.40.38`, `https://agent-communication.online`.
- Connection: existing local Alibaba Cloud Workbench profile, root user.
- Deployment directory: `/root/agent-collaboration-deploy`.
- Root Compose services: `platform`, `web`, `nginx`.
- Existing platform image: `sha256:a3f298bbd820a013be09b7501c03d2334b336a4128220e773c8075ffb1167d69`.
- Platform PeerID: `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`.
- Data volume: `/var/lib/docker/volumes/agent-collaboration-deploy_platform_data/_data`.

Preflight found all three containers running with zero restarts. Internal and
public health checks passed. SQLite quick checks passed; Registry had three rows
and MQ had six. The original four identity files were fingerprinted for comparison
after the switch. No private key content or message content was retrieved.

## Prepared release

- Release ID: `registry-ownership-20260913-c93fa234`.
- Local artifacts: `build/registry-ownership-release/`.
- Server release directory:
  `/root/agent-comm-releases/registry-ownership-20260913-c93fa234`.
- Platform base: `52b93e4da2b97ee5445127017f6b4c842da3433c`.
- SDK base: `0f94961bb0cce0a0c9f0c5016a6583156d383ec6`.
- Source snapshot: 159 files, 25 changed or added files, verified by
  `source-manifest.json`. At deployment time, the patch had not yet been committed
  or published to GitHub; the manifest records its exact content relative to these
  revisions. The subsequent source commits are recorded below.
- Build: Go 1.25.7, `linux/amd64`, `CGO_ENABLED=0`, `-trimpath`, from the source
  snapshot. Both modules' complete Go test suites passed before packaging.
- Platform SHA-256:
  `c93fa234d0662dc05138483205a5eee654074bd2c292a8ee1e659a1ccb4696f3`.
- Payload SHA-256:
  `c25896e9b2cec3c394c59f661adb30f1cd72d4945e8442fda6ed048626e3b03d`.

The payload contains the program, source snapshot, per-file manifest, reviewed
preparation/switch scripts, and a smoke-test program. It contains no identity PEM
files, production database files, `.env`, or Git credential metadata.

## Source publication

The SDK and platform fixes were subsequently committed and pushed to
`codex/registry-ownership`, then fast-forwarded into their default branches at the
user's request:

- SDK (`master`): [`150c0934b97feadd020f38ee374a39840afc8e11`](https://github.com/BillShiyaoZhang/agent-comm/commit/150c0934b97feadd020f38ee374a39840afc8e11).
- Platform (`main`): [`5676992028830823c4945a7fb0aa8364b0655acd`](https://github.com/BillShiyaoZhang/agent-comm-platform/commit/5676992028830823c4945a7fb0aa8364b0655acd).

The platform commit pins the SDK commit above. The deployment repository's
`main` branch pins that platform commit and includes this
record. All 159 local source files matched the deployment manifest before
publication, using its documented line-ending normalization. Publication does
not replace the running image or change the production data.

## Switch and recovery plan

Prepare the small runtime image from the current known image without compiling
on the server. Retain the old image tag. Then stop only platform, archive its
whole data volume consistently, save production configuration and original
changed source files in a root-only backup directory, apply the verified patch,
and recreate only platform using the original root Compose file and mounts.
Verify health, original identity fingerprints, mount properties, source hashes,
database integrity, and unchanged web/nginx container identities. Reload nginx
after testing its configuration so its upstream resolves the new platform IP.

The reviewed switch script attempts to restore the previous image if switching
or verification fails. Source restoration errors do not prevent that runtime
recovery attempt. Database backups are retained for recovery; normal program
rollback preserves the current database to avoid losing new messages.

Completed backup directory:
`/root/agent-comm-backups/registry-ownership-20260913-c93fa234`.

Consistent data archive SHA-256:
`68c3db6e3b2f3685f7e9424521a4dd7621d034e95aa59b7f527dc52e5982c0a5`.

The preserved old image tag is
`agent-platform:pre-registry-ownership-20260913-c93fa234`. A program-only rollback
can use it without restoring databases or discarding newly arrived messages:

```bash
cd /root/agent-collaboration-deploy
docker image tag agent-platform:pre-registry-ownership-20260913-c93fa234 agent-collaboration-deploy-platform:latest
docker compose up -d --no-deps --no-build platform
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

That old image contains the original ownership vulnerability. The source patch
remains on disk after a program-only rollback; the backup also includes original
source files if a separate source rollback is needed.

Preparation stopped safely before touching production when it encountered an
upstream SDK file committed with CRLF line endings. The file matched its Git
revision exactly. The operational scripts were corrected to apply the source
manifest's text normalization while preserving exact hashes for other files.
The final script update archive was `operations-v3.tar.gz`, SHA-256
`c12e6e1500720adedfe98c0d608fdb81b42f9e871a6a34150035863c68d95704`.
The program and application source snapshot did not change during that correction.

## Post-switch verification

The supplied smoke program was run from the Windows workstation against the
public HTTPS origin and `8.130.40.38:45041`. It creates random
`urn:registry-deploy-smoke` identities, checks that
owner registration and message preparation work, rejects another identity's
overwrite and first claim, compares the original record including TTL, and
verifies a signed owner update. It never sends a message. The exact emitted test
URNs were inspected and removed, and final health and release metadata were saved.
