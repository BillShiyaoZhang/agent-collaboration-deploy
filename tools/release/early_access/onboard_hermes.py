"""Install and connect an existing Hermes, continuing after its terminal exits.

The local identity signs a short-lived Web pairing request. Only the signed,
exact grant approved on its claim page is installed. No shell command, owner
identity, key, or permission is accepted from a polled response.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid

from install import ensure_hermes, utf8_output, verify_bundle

PROTOCOL = "agent-comm-onboarding/v1"
DEFAULT_PLATFORM = "https://agent-communication.online"


def emit(**data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def private_json(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Onboarding state must not be a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".onboarding-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def local_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.write(b"0")
            stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def clean_environment(home=None, source=None):
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONHOME", "PYTHONPATH"}}
    if home is not None:
        env["HERMES_HOME"] = str(home)
    if source is not None:
        env["PYTHONPATH"] = str(source)
    return env


def launcher_interpreters(launcher):
    """Read known launchers; never execute or expand shell content to discover Python."""
    path = Path(launcher).expanduser().absolute()
    candidates = [path.parent / "python", path.parent / "python.exe",
                  path.parent / "venv/bin/python", path.parent / "venv/Scripts/python.exe"]
    try:
        text = path.read_text(encoding="utf-8")[:16384]
    except (OSError, UnicodeError):
        text = ""
    for line in text.splitlines():
        try:
            words = shlex.split(line[2:] if line.startswith("#!") else line)
        except ValueError:
            continue
        candidate = words[1] if len(words) > 1 and words[0] == "exec" else (words[0] if words else "")
        if candidate and Path(candidate).is_absolute() and "python" in Path(candidate).name.lower():
            candidates.insert(0, Path(candidate))
    return [str(item) for item in candidates if item.is_file()]


def select_python(explicit=None):
    if explicit:
        candidates = [str(Path(explicit).expanduser().absolute())]
    else:
        candidates = [sys.executable]
        launcher = shutil.which("hermes")
        if launcher:
            candidates.extend(launcher_interpreters(launcher))
    probe = ("import sys; sys.path.insert(0, sys.argv[1]); from install import ensure_hermes; "
             "c, _ = ensure_hermes(); import json; "
             "print(json.dumps({'python': sys.executable, 'home': str(c.get_hermes_home())}))")
    for candidate in dict.fromkeys(candidates):
        try:
            result = subprocess.run([candidate, "-c", probe, str(Path(__file__).resolve().parent)],
                                    env=clean_environment(), capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout.strip().splitlines()[-1])
                return data["python"]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    raise RuntimeError("Cannot find a supported Hermes interpreter. Pass --python with the Python used by the Hermes launcher")


def public_platform(value):
    parsed = urlsplit(value)
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if (parsed.scheme != "https" and not (parsed.scheme == "http" and local)) or not parsed.hostname:
        raise ValueError("The public platform must use HTTPS (HTTP is allowed only for local tests)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.rstrip("/"):
        raise ValueError("The public platform must be a plain origin without credentials or a path")
    return value.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Onboarding endpoints must not redirect signed requests or polling credentials")


def request_json(url, *, body=None, authorization=None):
    headers = {"Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    if body is not None:
        headers["Content-Type"] = "application/json"
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(Request(url, data=body, headers=headers), timeout=30) as response:
        payload = response.read(262145)
    if len(payload) > 262144:
        raise ValueError("Onboarding response is too large")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("Onboarding response must be a JSON object")
    return value


def run_json(command):
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or value.get("error"):
        raise RuntimeError("The helper did not complete the requested identity operation")
    return value


def detached(command, log, *, home, source=None):
    log.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    with log.open("ab", buffering=0) as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                   cwd=home, env=clean_environment(home, source), close_fds=True, **kwargs)
    return process


def retain_bundle(bundle, home):
    root, _ = verify_bundle(bundle)
    digest = hashlib.sha256((root / "SHA256SUMS.json").read_bytes()).hexdigest()[:20]
    destination = home / "agent-comm" / "releases" / digest
    if destination.is_dir():
        verify_bundle(destination)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".release-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        manifest = json.loads((root / "SHA256SUMS.json").read_text())
        for name in [*manifest["files"], "SHA256SUMS.json"]:
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
        staged.rename(destination)
    return destination


def serve_helper(path):
    """One supervisor per identity, independent of the installing Hermes turn."""
    path = Path(path).resolve()
    state = json.loads(path.read_text())
    from configure_hermes import helper_info
    with local_lock(path.with_suffix(".lock")):
        while True:
            try:
                _, actual = helper_info(state["helper_url"])
                if actual != state["agent_urn"]:
                    raise RuntimeError("Helper port has been taken by another identity")
                time.sleep(5)
                continue
            except (OSError, ValueError):
                pass
            command = [state["helper"], "daemon", state["identity_dir"], state["platform"], str(state["port"])]
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, close_fds=True,
                                     cwd=state["home"], env=clean_environment(state["home"]))
            child.wait()
            time.sleep(5)


def start_helper_supervisor(state, bundle, home):
    path = home / "agent-comm" / "helper-service.json"
    private_json(path, state)
    log = home / "agent-comm" / "logs" / "helper.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(bundle / "onboard_hermes.py"), "--serve-helper", str(path)]
    if sys.platform == "darwin" and shutil.which("launchctl"):
        label = "online.agent-communication.helper." + hashlib.sha256(str(home).encode()).hexdigest()[:16]
        plist_path = Path.home() / "Library" / "LaunchAgents" / (label + ".plist")
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        content = {"Label": label, "ProgramArguments": command, "RunAtLoad": True, "KeepAlive": True,
                   "WorkingDirectory": str(home), "StandardOutPath": str(log), "StandardErrorPath": str(log),
                   "EnvironmentVariables": {"HERMES_HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}}
        # This label is scoped to this exact profile. Reuse a live existing job;
        # never boot out the helper just because an installer was run twice.
        if not plist_path.exists() or plist_path.read_bytes() != plistlib.dumps(content):
            plist_path.write_bytes(plistlib.dumps(content))
        domain = f"gui/{os.getuid()}"
        with log.open("ab") as stream:
            subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], stdout=stream, stderr=stream, timeout=30)
            result = subprocess.run(["launchctl", "kickstart", domain + "/" + label], stdout=stream, stderr=stream, timeout=30)
        if result.returncode == 0:
            return None
    # Works on Linux/Windows and headless macOS without a launchd GUI domain.
    # State and restart commands remain on disk; this fallback does not promise
    # reboot persistence on hosts without an available service manager.
    return detached(command, log, home=home)


def ensure_helper(bundle, home, origin, previous, requested_port=None):
    from configure_hermes import helper_info, ensure_platform_registration
    data = home / "agent-comm" / "identity"
    helper = bundle / ("agent-comm-helper.exe" if os.name == "nt" else "agent-comm-helper")
    if os.name != "nt":
        helper.chmod(helper.stat().st_mode | 0o100)
    identity = run_json([str(helper), "init", str(data)])
    urn = identity["urn"]
    if previous and previous.get("agent_urn") != urn:
        raise ValueError("Saved onboarding identity differs from the local helper; no identity was replaced")
    saved_port = previous.get("port") if previous else None
    if saved_port and requested_port and saved_port != requested_port:
        raise ValueError("This profile already owns a helper port; rerun without --port to preserve its connection")
    port = requested_port or saved_port or 45042
    url = f"http://127.0.0.1:{port}"
    try:
        _, running_urn = helper_info(url)
    except (OSError, ValueError):
        running_urn = None
    if running_urn is not None and running_urn != urn:
        if saved_port or requested_port:
            raise ValueError("The selected helper port belongs to a different identity")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        running_urn = None
    process = None
    if running_urn is None:
        process = start_helper_supervisor({"helper": str(helper), "identity_dir": str(data), "platform": origin,
                                          "home": str(home), "port": port, "helper_url": url, "agent_urn": urn}, bundle, home)
    for _ in range(60):
        try:
            _, actual = helper_info(url)
            if actual != urn:
                raise RuntimeError("The helper listener changed identity during startup")
            ensure_platform_registration(url, urn)
            return {"agent_urn": urn, "port": port, "helper_url": url, "identity_dir": str(data), "helper": str(helper)}
        except (OSError, ValueError) as exc:
            if process is not None and process.poll() is not None:
                raise RuntimeError(f"Helper exited; see {home / 'agent-comm/logs/helper.log'}") from exc
            time.sleep(1)
    raise RuntimeError(f"Helper registration did not become ready; see {home / 'agent-comm/logs/helper.log'}")


def fingerprint(public_key):
    digest = hashlib.sha256(public_key).digest()[:16]
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number, result = int.from_bytes(digest, "big"), ""
    while number:
        number, digit = divmod(number, 58)
        result = alphabet[digit] + result
    return "1" * (len(digest) - len(digest.lstrip(b"\0"))) + result


def verify_grant(response, state):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from agent_comm_runtime.identity import validate_urn
    from agent_comm_runtime.remote import instant
    raw = response.get("grant")
    if not isinstance(raw, str) or len(raw) > 16384:
        raise ValueError("A signed grant is required")
    public_key = bytes.fromhex(response["public_key"])
    signature = bytes.fromhex(response["signature"])
    if len(public_key) != 32 or len(signature) != 64:
        raise ValueError("Invalid grant signature encoding")
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, raw.encode("utf-8"))
    grant = json.loads(raw)
    for key in ("protocol", "request_id", "agent_urn", "methods", "expires_at"):
        expected = PROTOCOL if key == "protocol" else state[key]
        if grant.get(key) != expected:
            raise ValueError(f"The Web grant changed the requested {key}")
    console = validate_urn(grant.get("console_urn"))
    if console.rsplit(":", 1)[-1] != fingerprint(public_key):
        raise ValueError("Console identity does not match the grant signing key")
    if instant(grant["expires_at"]) <= time.time():
        raise ValueError("The approved pairing has expired")
    return grant


def live_gateway_pid(home):
    from gateway import status
    probe = getattr(status, "live_gateway_pid_for_home", None)
    return probe(home) if callable(probe) else status.get_running_pid(home / "gateway.pid", cleanup_stale=False)


def gateway_connected(home):
    from gateway.status import read_runtime_status, runtime_status_is_stale, runtime_status_pid_is_live
    status = read_runtime_status(home / "gateway_state.json")
    return bool(status and not runtime_status_is_stale(status) and runtime_status_pid_is_live(status)
                and status.get("pid") == live_gateway_pid(home)
                and status.get("platforms", {}).get("agent_comm", {}).get("state") == "connected")


def ensure_gateway(home, source, *, restart=False):
    entrypoint = source / "hermes"
    command = [sys.executable, str(entrypoint)] if entrypoint.is_file() else [sys.executable, "-m", "hermes_cli.main"]
    env = clean_environment(home, source)
    logs = home / "agent-comm" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    pid = live_gateway_pid(home)
    if pid and restart:
        # Use the host's draining restart; never kill an unrelated process or
        # bypass the host's active-turn / service-manager checks.
        with (logs / "gateway-start.log").open("ab") as stream:
            subprocess.run([*command, "gateway", "restart"], stdin=subprocess.DEVNULL,
                           stdout=stream, stderr=stream, env=env, cwd=source, timeout=240, check=True)
    elif not pid:
        with (logs / "gateway-start.log").open("ab") as stream:
            result = subprocess.run([*command, "gateway", "start"], stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=stream, env=env, cwd=source, timeout=90)
        # Minimal Linux/container hosts may have no service manager. Keep the
        # foreground runtime in its own session, with durable logs and PID data.
        for _ in range(10):
            if live_gateway_pid(home):
                break
            time.sleep(1)
        if not live_gateway_pid(home):
            detached([*command, "gateway", "run"], logs / "gateway.log", home=home, source=source)
    for _ in range(90):
        if gateway_connected(home):
            return
        time.sleep(1)
    raise RuntimeError(f"Agent Comm Gateway did not connect; inspect {logs}")


def pairing_matches(state, grant):
    """A recorded success is not proof that its local permission still exists."""
    from agent_comm_runtime.remote import RemoteBridge, hermes_principal, instant
    _, config = ensure_hermes()
    home = Path(state["home"])
    current = config.require_readable_config_before_write(config.get_config_path())
    platform_config = current.get("platforms", {}).get("agent_comm", {})
    extra = platform_config.get("extra", {})
    settings = {**extra, **{key: value for key, value in platform_config.items() if key != "extra"}}
    if (settings.get("enabled") is not True or settings.get("remote_enabled") is not True
            or settings.get("urn") != state["agent_urn"] or settings.get("platform_url") != state["helper_url"]
            or grant["console_urn"] not in settings.get("allow_from", [])):
        return False
    path = Path(settings.get("remote_state_path") or home / "agent-comm/remote.sqlite3")
    if not path.is_file() or instant(grant["expires_at"]) <= time.time():
        return False
    bridge = RemoteBridge(path, None, state["agent_urn"], bound_principal=hermes_principal(home))
    try:
        return any(pair.get("console_urn") == grant["console_urn"]
                   and pair.get("revoked") is False
                   and pair.get("owner_principal") == hermes_principal(home)
                   and set(pair.get("methods", [])) == set(grant["methods"])
                   and pair.get("expires_at") == grant["expires_at"] for pair in bridge.pairings())
    finally:
        bridge.close()


def complete_pairing(state, grant, checkpoint=lambda: None):
    import configure_hermes
    home = Path(state["home"])
    args = ["--helper-url", state["helper_url"], "--remote", "--pair-console", grant["console_urn"],
            "--expires", grant["expires_at"]]
    if state["allow_web_actions"]:
        args.append("--allow-web-actions")
    already_paired = pairing_matches(state, grant)
    if state.get("local_pair_installed") and not already_paired:
        raise ValueError("The local pairing was revoked or changed during onboarding; a new Web approval is required")
    if not already_paired and configure_hermes.main(args) != 0:
        raise RuntimeError("The approved local pairing could not be saved")
    state["local_pair_installed"] = True
    checkpoint()
    if state.get("gateway_ready_for_request") != state["request_id"] or not gateway_connected(home):
        ensure_gateway(home, Path(state["source"]), restart=True)
        state["gateway_ready_for_request"] = state["request_id"]


def acknowledge_connection(path, state, endpoint, deadline):
    while time.time() < deadline:
        try:
            request_json(endpoint, authorization="Bearer " + state["poll_secret"], body={"status": "completed"})
            state["web_ack_pending"] = False
            private_json(path, state)
            return
        except (OSError, ValueError):
            time.sleep(5)
    emit(status="connected", web_acknowledgement="pending")


def poll_pairing(path):
    path = Path(path).expanduser().resolve()
    with local_lock(path.with_suffix(".worker.lock")):
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("status") == "connected" and not state.get("web_ack_pending"):
            return
        os.environ["HERMES_HOME"] = state["home"]
        ensure_hermes()
        endpoint = public_platform(state["platform"]) + "/api/onboarding/" + str(uuid.UUID(state["request_id"]))
        # The server permits already-approved grants a bounded completion grace
        # period. Unapproved requests still expire at ticket_expires_at.
        deadline = datetime.fromisoformat(state["ticket_expires_at"].replace("Z", "+00:00")).timestamp() + 1800
        if state.get("status") == "connected":
            acknowledge_connection(path, state, endpoint, deadline)
            return
        try:
            while time.time() < deadline:
                response = state.get("approval")
                if response is None:
                    try:
                        response = request_json(endpoint, authorization="Bearer " + state["poll_secret"])
                    except HTTPError as exc:
                        if exc.code not in {429, 500, 502, 503, 504}:
                            raise
                        time.sleep(5)
                        continue
                    except (URLError, TimeoutError):
                        time.sleep(5)
                        continue
                if response.get("status") == "pending":
                    time.sleep(2)
                    continue
                if response.get("status") not in {"approved", "completed"}:
                    raise RuntimeError("The Web pairing request is no longer pending or approved")
                grant = verify_grant(response, state)
                if state.get("approval") is None:
                    state.update(status="approved", approval=response)
                    private_json(path, state)
                try:
                    complete_pairing(state, grant, checkpoint=lambda: private_json(path, state))
                except (RuntimeError, OSError, subprocess.SubprocessError):
                    # The signed grant survives transient helper/Gateway failure;
                    # retry within the ticket window without another owner action.
                    time.sleep(5)
                    continue
                state.update(status="connected", console_urn=grant["console_urn"], web_ack_pending=True,
                             completed_at=datetime.now(timezone.utc).isoformat())
                state.pop("error", None)
                private_json(path, state)
                # The local result is durable before acknowledging Web. A lost
                # completion response must never erase a working local pairing.
                acknowledge_connection(path, state, endpoint, deadline)
                emit(status="connected", agent_urn=state["agent_urn"], console_urn=grant["console_urn"])
                return
            raise RuntimeError("Web confirmation expired; rerun onboarding to create a new claim page")
        except Exception as exc:
            # Avoid reflecting remote bodies, tokens, or private configuration.
            state.update(status="error", error=type(exc).__name__ + ": " + str(exc)[:300])
            private_json(path, state)
            raise


def brief(state):
    return {key: state[key] for key in ("status", "agent_urn", "claim_url", "ticket_expires_at", "console_urn", "error") if key in state}


def onboard(args):
    constants, config = ensure_hermes()
    home = Path(constants.get_hermes_home()).expanduser().resolve()
    source = Path(constants.__file__).resolve().parent
    origin = public_platform(args.platform)
    root = home / "agent-comm"
    state_path = root / "onboarding.json"
    root.mkdir(parents=True, exist_ok=True)
    with local_lock(root / "onboarding.setup.lock"):
        previous = json.loads(state_path.read_text()) if state_path.is_file() else None
        if args.status:
            if previous is None:
                raise RuntimeError("No onboarding state exists for this Hermes profile")
            emit(**brief(previous), gateway_connected=gateway_connected(home))
            return
        if previous and previous["platform"] != origin:
            raise ValueError("This profile already uses a different platform; do not replace its identity or pairing")
        original = config.require_readable_config_before_write(config.get_config_path())
        existing = original.get("platforms", {}).get("agent_comm", {})
        existing_urn = existing.get("urn") or existing.get("extra", {}).get("urn")
        if existing_urn and (not previous or previous.get("agent_urn") != existing_urn):
            raise ValueError("This profile already has a manually managed Agent Comm identity; use configure_hermes.py to preserve it")
        bundle = retain_bundle(args.bundle_dir, home)
        subprocess.run([sys.executable, str(bundle / "install.py")], check=True, env=clean_environment(home, source))
        from configure_hermes import PAIR_METHODS, WEB_ACTION_METHODS
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # Verify host prerequisite before creating a request.
        helper = ensure_helper(bundle, home, origin, previous, args.port)
        if previous and previous.get("status") == "connected" and previous.get("approval"):
            try:
                grant = verify_grant(previous["approval"], previous)
                valid = pairing_matches(previous, grant)
            except ValueError:
                valid = False
            if valid:
                ensure_gateway(home, source, restart=True)
                if previous.get("web_ack_pending"):
                    detached([sys.executable, str(bundle / "onboard_hermes.py"), "--resume", str(state_path)],
                             root / "logs" / "onboarding.log", home=home, source=source)
                emit(**brief(previous), gateway_connected=True)
                return
        pending = (previous and previous.get("status") in {"pending", "approved", "error"}
                   and datetime.fromisoformat(previous["ticket_expires_at"].replace("Z", "+00:00")).timestamp() > time.time())
        if pending:
            state = previous
        else:
            methods = [*PAIR_METHODS, *(WEB_ACTION_METHODS if args.allow_web_actions else [])]
            expires = (datetime.now(timezone.utc) + timedelta(days=args.pair_days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            secret = secrets.token_hex(32)
            body = json.dumps({"protocol": PROTOCOL, "agent_urn": helper["agent_urn"], "name": args.name,
                               "poll_secret_hash": hashlib.sha256(secret.encode()).hexdigest(), "methods": methods,
                               "expires_at": expires, "timestamp": int(time.time())}, separators=(",", ":"), ensure_ascii=False).encode()
            signed = run_json([helper["helper"], "sign-store", helper["identity_dir"], body.hex()])
            response = request_json(origin + "/api/onboarding", body=body,
                                    authorization="Ed25519 " + signed["signature"] + ":" + signed["pubkey"])
            request_id = str(uuid.UUID(response["request_id"]))
            claim_url = response["claim_url"]
            parsed = urlsplit(claim_url)
            if (parsed.scheme, parsed.netloc) != (urlsplit(origin).scheme, urlsplit(origin).netloc) or not parsed.path.startswith("/connect/") or parsed.query or parsed.fragment:
                raise ValueError("The claim page must remain on the requested platform")
            deadline = datetime.fromisoformat(response["expires_at"].replace("Z", "+00:00")).timestamp()
            if not time.time() < deadline <= time.time() + 1800:
                raise ValueError("Invalid short-lived pairing deadline")
            state = {"status": "pending", "home": str(home), "source": str(source), "bundle": str(bundle),
                     "platform": origin, **helper, "request_id": request_id, "claim_url": claim_url,
                     "ticket_expires_at": response["expires_at"], "poll_secret": secret, "methods": methods,
                     "expires_at": expires, "allow_web_actions": args.allow_web_actions}
            private_json(state_path, state)
        detached([sys.executable, str(bundle / "onboard_hermes.py"), "--resume", str(state_path)],
                 root / "logs" / "onboarding.log", home=home, source=source)
        emit(**brief(state), profile=str(home),
             instruction="Open claim_url in the signed-in Web account and confirm. The local worker will pair and start Gateway automatically; no further Hermes command is needed.")


def main(argv=None):
    utf8_output()
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--python", help="Actual Hermes Python; discovered from current interpreter or hermes launcher when omitted")
    cli.add_argument("--hermes-home", help="Explicit profile; otherwise preserve HERMES_HOME and Hermes's native profile resolution")
    cli.add_argument("--bundle-dir", type=Path, default=Path(__file__).resolve().parent)
    cli.add_argument("--platform", default=DEFAULT_PLATFORM)
    cli.add_argument("--name", default="Hermes")
    cli.add_argument("--port", type=int)
    cli.add_argument("--pair-days", type=int, default=7, choices=range(1, 31))
    cli.add_argument("--allow-web-actions", action="store_true")
    cli.add_argument("--status", action="store_true")
    cli.add_argument("--resume", type=Path, help=argparse.SUPPRESS)
    cli.add_argument("--serve-helper", type=Path, help=argparse.SUPPRESS)
    args = cli.parse_args(argv)
    try:
        if args.port is not None and not 1024 <= args.port <= 65535:
            raise ValueError("--port must be between 1024 and 65535")
        if args.hermes_home:
            os.environ["HERMES_HOME"] = str(Path(args.hermes_home).expanduser().resolve())
        if args.serve_helper:
            serve_helper(args.serve_helper)
        elif args.resume:
            poll_pairing(args.resume)
        else:
            selected = select_python(args.python)
            # Do not resolve symlinks: a venv interpreter points at the base
            # Python, but selecting that resolved path loses the Hermes venv.
            if os.path.abspath(selected) != os.path.abspath(sys.executable):
                command = [selected, str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:])]
                return subprocess.run(command, env=clean_environment(), check=False).returncode
            onboard(args)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Onboarding stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
