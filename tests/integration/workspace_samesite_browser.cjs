// Real compiled NextAuth browser perimeter, using a fresh loopback fixture only.
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path");
const crypto = require("node:crypto"), https = require("node:https"), { createRequire } = require("node:module");
const web = path.resolve(__dirname, "../../agent-collaboration-web");
const { seedAccount } = require(path.join(web, "tests/integration/seed-account.cjs"));
const { chromium } = createRequire(process.env.WORKSPACE_BROWSER_PLAYWRIGHT_PACKAGE)("playwright");
const portal = process.env.WORKSPACE_PORTAL_FIXTURE_URL;
const attackPort = Number(process.env.WORKSPACE_BROWSER_ATTACK_PORT);
const nodeOrigin = `https://111111111111111111111111.workspace.example.com:${attackPort}`;
const otherNode = `https://222222222222222222222222.workspace.example.com:${attackPort}`;
assert.equal(new URL(portal).hostname, "portal.example.com");
assert.ok(attackPort > 1024 && attackPort < 65536);
const output = fs.realpathSync(path.join(web, "build/workspace-portal-preview"));
function fixtureFile(filename) {
  const real = fs.realpathSync(filename), relative = path.relative(output, real);
  assert.ok(relative && !relative.startsWith("..") && !path.isAbsolute(relative));
  return fs.readFileSync(real);
}
let browser, server, phase = "seed";
(async () => {
  const password = "Synthetic-" + crypto.randomBytes(18).toString("hex");
  const account = await seedAccount({ email: `browser-${Date.now()}@example.invalid`, password,
    database: process.env.WORKSPACE_PORTAL_FIXTURE_DATABASE });
  const seen = [];
  server = https.createServer({ cert: fixtureFile(process.env.WORKSPACE_PORTAL_FIXTURE_TLS_CERT),
    key: fixtureFile(process.env.WORKSPACE_PORTAL_FIXTURE_TLS_KEY) }, (req, res) => {
    seen.push({ host: req.headers.host, cookie: req.headers.cookie || "" });
    res.writeHead(200, { "Content-Type": "text/html", "Origin-Agent-Cluster": "?1", "Cross-Origin-Opener-Policy": "same-origin" });
    res.end("<!doctype html><title>Owned synthetic workspace</title>");
  });
  await new Promise((resolve, reject) => { server.once("error", reject); server.listen(attackPort, "127.0.0.1", resolve); });
  phase = "browser-launch";
  browser = await chromium.launch({ headless: true,
    ...(process.env.WORKSPACE_BROWSER_EXECUTABLE ? { executablePath: process.env.WORKSPACE_BROWSER_EXECUTABLE } : {}),
    args: ["--no-proxy-server", "--host-resolver-rules=MAP *.example.com 127.0.0.1,EXCLUDE localhost"] });
  phase = "browser-context";
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const allowed = new Set([portal, nodeOrigin, otherNode]);
  await context.route("**/*", route => allowed.has(new URL(route.request().url()).origin) ? route.continue() : route.abort());
  const page = await context.newPage();
  phase = "login-navigation";
  const login = await page.goto(portal + "/login?callbackUrl=%2Fdashboard%2Fworkspaces");
  assert.equal(login.status(), 200);
  assert.equal(login.headers()["origin-agent-cluster"], "?1");
  assert.equal(login.headers()["cross-origin-opener-policy"], "same-origin");
  phase = "login-fields";
  await page.locator("#email").fill(account.email);
  await page.locator("#password").fill(password);
  phase = "login-submit";
  await page.locator('button[type="submit"]').click();
  phase = "login-redirect";
  await page.waitForURL(url => url.pathname === "/dashboard/workspaces", { timeout: 30000 });
  const cookies = await context.cookies(portal);
  const session = cookies.find(cookie => cookie.name === "__Host-next-auth.session-token");
  assert.ok(session, "real credentials login must issue Host session cookie");
  for (const cookie of cookies.filter(cookie => cookie.name.startsWith("__Host-next-auth."))) {
    assert.equal(cookie.domain, "portal.example.com"); assert.equal(cookie.path, "/");
    assert.equal(cookie.secure, true); assert.equal(cookie.httpOnly, true); assert.equal(cookie.sameSite, "Lax");
  }
  assert.ok(!cookies.some(cookie => cookie.name === "__Secure-next-auth.session-token"));
  const identity = await page.evaluate(async () => (await fetch("/api/auth/session")).json());
  assert.equal(identity.user.id, account.id);
  const enrollment = await page.evaluate(async () => { const response = await fetch("/api/workspace-nodes/enroll", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    return { status: response.status, value: await response.json() }; });
  assert.equal(enrollment.status, 200);
  assert.equal(new URL(enrollment.value.gateway_url).hostname, "gateway.workspace.example.com");
  phase = "legacy-cookie-rejection";
  const legacy = await browser.newContext({ ignoreHTTPSErrors: true });
  await legacy.route("**/*", route => new URL(route.request().url()).origin === portal ? route.continue() : route.abort());
  await legacy.addCookies([{ name: "__Secure-next-auth.session-token", value: session.value,
    domain: "portal.example.com", path: "/", secure: true, httpOnly: true, sameSite: "Lax" }]);
  const legacyPage = await legacy.newPage();
  assert.equal((await legacyPage.goto(portal + "/api/workspace-nodes")).status(), 401);
  await legacy.close();
  phase = "sibling-cookie-injection";
  const currentSession = (await context.cookies(portal)).find(cookie => cookie.name === session.name);
  const node = await context.newPage(); await node.goto(nodeOrigin);
  assert.ok(!seen.some(value => value.cookie.includes("next-auth")), "portal Host cookies cannot reach sibling server");
  await node.evaluate(() => {
    document.cookie = "__Host-next-auth.session-token=attacker; Domain=example.com; Path=/; Secure; SameSite=Lax";
    document.cookie = "__Host-next-auth.csrf-token=attacker; Domain=example.com; Path=/; Secure; SameSite=Lax";
    document.cookie = "__Secure-next-auth.session-token=attacker; Domain=example.com; Path=/; Secure; SameSite=Lax";
    localStorage.setItem("fixture-node", "first");
    document.cookie = "__Host-workspace_session=first; Path=/; Secure; SameSite=Lax";
  });
  const after = await context.cookies(portal);
  assert.equal(after.find(cookie => cookie.name === session.name).value, currentSession.value);
  assert.ok(!after.some(cookie => cookie.name.startsWith("__Host-next-auth.") && cookie.domain === ".example.com"));
  assert.equal((await page.evaluate(async () => (await (await fetch("/api/auth/session")).json()).user.id)), account.id);
  phase = "real-fetch-metadata";
  async function denied(pathname, action) {
    const responsePromise = node.waitForResponse(response => response.url() === portal + pathname);
    await action(); const response = await responsePromise;
    assert.equal(response.status(), 403);
    const records = fs.readFileSync(process.env.WORKSPACE_PORTAL_FIXTURE_REQUEST_AUDIT_PATH, "utf8")
      .trim().split("\n").map(line => JSON.parse(line));
    const observed = records.findLast(record => record.path === pathname);
    assert.equal(observed.site, "same-site", "TLS server must observe the browser-generated Fetch Metadata");
    return observed;
  }
  const headers = await denied("/api/auth/session", () => node.evaluate(async url => {
    try { await fetch(url, { mode: "no-cors", credentials: "include" }); } catch {}
  }, portal + "/api/auth/session"));
  assert.equal(headers.hasHostSessionCookie, true, "browser sends portal cookie to same-site target; server guard rejects it");
  await denied("/api/auth/signout", () => node.evaluate(url => {
    const frame = document.createElement("iframe"); frame.name = "attack-form"; document.body.append(frame);
    const form = document.createElement("form"); form.action = url; form.method = "POST"; form.target = frame.name;
    document.body.append(form); form.submit();
  }, portal + "/api/auth/signout"));
  await denied("/login", () => node.evaluate(url => {
    const frame = document.createElement("iframe"); frame.src = url; document.body.append(frame);
  }, portal + "/login"));
  // Cookie-free same-site requests must also be denied before public routes.
  await context.clearCookies();
  await denied("/api/auth/csrf", () => node.evaluate(async url => {
    try { await fetch(url, { mode: "no-cors", credentials: "omit" }); } catch {}
  }, portal + "/api/auth/csrf"));
  phase = "node-origin-isolation";
  await node.evaluate(() => { document.cookie = "__Host-workspace_session=first; Path=/; Secure; SameSite=Lax"; });
  const second = await context.newPage(); await second.goto(otherNode);
  assert.equal(await second.evaluate(() => localStorage.getItem("fixture-node")), null);
  assert.ok(!seen.filter(value => value.host.startsWith("222222")).some(value => value.cookie.includes("workspace_session")));
  await context.close();
  console.log("WORKSPACE_SAMESITE_BROWSER_PASS real HTTPS credentials/BFF, Host cookie flags, legacy rejection, Domain injection refusal, browser same-site fetch/form/iframe denial, cookie-free guard, per-node storage/cookies");
})().catch(() => { console.error("WORKSPACE_SAMESITE_BROWSER_FAIL phase=" + phase); process.exitCode = 1; })
.finally(async () => { await browser?.close(); if (server) await new Promise(resolve => server.close(resolve)); });
