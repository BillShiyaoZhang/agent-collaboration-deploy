#!/usr/bin/env node
"use strict";

// This compatibility entry point deliberately has no installation capabilities.
const path = require("node:path");
const sdk = path.resolve(__dirname, "../../../agent-comm-platform/agent-comm");

process.stderr.write([
  "RETIRED: the deployment repository's agent-comm-cli no longer installs connectors.",
  "Its old cloud MQ protocol and automatic profile configuration are unsupported.",
  "Nothing was installed, downloaded, or configured.",
  "",
  "Hermes migration:",
  `1. Build/start the current helper from ${sdk}, preserving existing keys and mailbox.db.`,
  "2. In the Python environment running Hermes Gateway, run:",
  `   python -m pip install --upgrade \"${path.join(sdk, "connectors/hermes-platform")}\"`,
  "3. Confirm the actual HERMES_HOME; configure plugins.enabled, an explicit allow_from,",
  "   and platforms.agent_comm.extra.platform_url: http://127.0.0.1:45042.",
  "   The cloud platform URL belongs in the helper daemon configuration only.",
  `4. Follow ${path.join(sdk, "connectors/hermes-platform/README.md")} and verify real SSE connected status.`,
  "",
  "Do not use either repository's old generic connector CLI for this migration.",
  "The deployment repository's OpenClaw copy is also retired; maintained source lives in the SDK.",
  `Migration guide: ${path.resolve(__dirname, "../../README.md")}`,
  "",
].join("\n"));
process.exitCode = 1;
