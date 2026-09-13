"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const cli = path.resolve(__dirname, "../bin/cli.js");
const openclaw = path.resolve(__dirname, "../../openclaw-channel");

function snapshot(directory) {
  const files = {};
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const item = path.join(directory, entry.name);
    files[entry.name] = entry.isDirectory() ? snapshot(item) : fs.readFileSync(item).toString("hex");
  }
  return files;
}

function assertMigration(result) {
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /RETIRED/);
  assert.doesNotMatch(result.stdout, /Setup completed successfully/);
}

test("retired CLI cannot access filesystem, network, or subprocess capabilities", () => {
  let output = "";
  const sandbox = {
    __dirname: path.dirname(cli),
    require(name) {
      assert.equal(name, "node:path", `forbidden installation capability: ${name}`);
      return path;
    },
    process: { stderr: { write(text) { output += text; } }, exitCode: 0 },
  };
  vm.runInNewContext(fs.readFileSync(cli, "utf8"), sandbox, { timeout: 1000 });
  assert.equal(sandbox.process.exitCode, 1);
  assert.match(output, /python -m pip install --upgrade/);
  assert.match(output, /platforms\.agent_comm\.extra\.platform_url: http:\/\/127\.0\.0\.1:45042/);
  assert.match(output, /actual HERMES_HOME/);
});

for (const framework of ["Hermes", "OpenClaw", "unknown"]) {
  test(`old CLI fails without changing a ${framework} profile, identity, or dependencies`, (t) => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), "agent-comm-retired-cli-"));
    t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
    fs.writeFileSync(path.join(directory, "config.yaml"), "preserve: existing-configuration\n");
    fs.writeFileSync(path.join(directory, "settings.json"), '{"preserve":true}\n');
    fs.mkdirSync(path.join(directory, "keys"));
    fs.writeFileSync(path.join(directory, "keys", "identity.fixture"), "existing-identity-fixture");
    fs.writeFileSync(path.join(directory, "keys", "mailbox.fixture"), "existing-message-state");
    if (framework === "OpenClaw") {
      fs.writeFileSync(path.join(directory, "package.json"), '{"name":"fixture","private":true}\n');
    } else if (framework === "unknown") {
      fs.renameSync(path.join(directory, "config.yaml"), path.join(directory, "unrelated.txt"));
    }
    const before = snapshot(directory);
    for (const args of [[], ["init", "--keys-dir", path.join(directory, "keys")], ["--help"]]) {
      const result = spawnSync(process.execPath, [cli, ...args], {
        cwd: directory,
        encoding: "utf8",
        timeout: 5000,
        env: { ...process.env, HOME: directory, USERPROFILE: directory, HERMES_HOME: directory },
      });
      assertMigration(result);
      assert.match(result.stderr, /SDK|agent-comm-platform[\\/]agent-comm/);
      assert.deepEqual(snapshot(directory), before);
    }
  });
}

test("old OpenClaw package import and installation guard fail explicitly", () => {
  const imported = spawnSync(process.execPath, ["-e", "require(process.argv[1])", openclaw], {
    encoding: "utf8", timeout: 5000,
  });
  assertMigration(imported);
  assert.match(imported.stderr, /maintained connector source/);
  const guard = spawnSync(process.execPath, [path.join(openclaw, "retired.js")], {
    encoding: "utf8", timeout: 5000,
  });
  assertMigration(guard);
});
