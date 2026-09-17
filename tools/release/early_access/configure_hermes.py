"""Explicit local setup of Hermes collaboration and optional remote pairing.

Reads the helper's loopback /info endpoint and Hermes configuration. Pairing
automatically registers the existing local identity through the helper. Keys,
mailboxes and existing collaboration databases are preserved. --remote by itself
does not trust any console. --pair-console is an explicit local grant.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid

from install import ensure_hermes, utf8_output

PAIR_METHODS = ["capabilities", "contacts.list", "contacts.requests", "collaboration.state", "inbox.list", "attention.list", "conversation.send", "conversation.get"]
WEB_ACTION_METHODS = ["contacts.add", "contacts.respond", "messages.send", "inbox.mark_read", "approval.respond", "collaboration.execute"]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("The local helper must not redirect configuration requests")


def helper_info(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/api/v1/mq"}):
        raise ValueError("--helper-url must be loopback HTTP, without credentials, query or fragment")
    host = "[::1]" if parsed.hostname == "::1" else "127.0.0.1"
    base = f"http://{host}" + (f":{parsed.port}" if parsed.port is not None else "")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(Request(base + "/info", headers={"Accept": "application/json"}), timeout=10) as response:
        payload = response.read(262145)
    if len(payload) > 262144:
        raise ValueError("Helper info response is unexpectedly large")
    info = json.loads(payload)
    if not isinstance(info, dict):
        raise ValueError("Helper info must be a JSON object")
    from agent_comm_runtime.identity import validate_urn
    return base, validate_urn(info.get("urn"))


def mapping(parent, name):
    value = parent.get(name)
    if value is None:
        value = {}
        parent[name] = value
    if not isinstance(value, dict):
        raise ValueError(f"Existing {name} configuration is not a mapping; no configuration was overwritten")
    return value


def ensure_platform_registration(helper_url, urn):
    """Ask the local key owner to sign registration; never create a cloud agent."""
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(helper_url + "/api/v1/platform/register", data=b"{}",
                      headers={"Content-Type": "application/json"}, method="POST")
    with opener.open(request, timeout=15) as response:
        payload = response.read(262145)
    if len(payload) > 262144:
        raise ValueError("Helper registration response is unexpectedly large")
    result = json.loads(payload)
    if not isinstance(result, dict) or result.get("registered") is not True or result.get("urn") != urn:
        raise ValueError("The helper did not confirm registration of this local agent")


def install_attention_companion(home):
    """Install the matching bundled local UI; retain any previous plugin intact."""
    from importlib.resources import files
    from hermes_platform_agent_comm.companion_export import ASSETS
    source = files("hermes_platform_agent_comm").joinpath("companion")
    payloads = {name: source.joinpath(name).read_bytes() for name in ASSETS}
    plugins = home / "plugins"
    target = plugins / "agent-comm-attention"
    if plugins.is_symlink() or target.is_symlink():
        raise ValueError("Attention plugin installation needs a real local directory, not a symlink")
    if target.exists() and not target.is_dir():
        raise ValueError("Attention plugin path is not a directory")
    if target.is_dir() and all((target / name).is_file() and (target / name).read_bytes() == data for name, data in payloads.items()):
        return target
    plugins.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix=".agent-comm-attention-stage-", dir=plugins) as stage:
        staged = Path(stage) / "agent-comm-attention"
        for name, data in payloads.items():
            destination = staged / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        if target.exists():
            backup = plugins / (".agent-comm-attention-backup-" + uuid.uuid4().hex)
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
    return target


def merge_config(original, *, helper_url, urn, peers, remote):
    from agent_comm_runtime.identity import validate_urn
    result = copy.deepcopy(original)
    plugins = mapping(result, "plugins")
    enabled = plugins.get("enabled") or []
    if not isinstance(enabled, list) or any(not isinstance(item, str) for item in enabled):
        raise ValueError("plugins.enabled must be a list before setup can safely merge it")
    plugins["enabled"] = list(dict.fromkeys([*enabled, "agent_comm", "agent-comm-attention"]))
    if "disabled" in plugins:
        if not isinstance(plugins["disabled"], list):
            raise ValueError("plugins.disabled must be a list")
        plugins["disabled"] = [name for name in plugins["disabled"] if name not in {"agent_comm", "agent-comm-attention"}]
    platform = mapping(mapping(result, "platforms"), "agent_comm")
    extra = mapping(platform, "extra")
    existing_peers = platform.get("allow_from", extra.get("allow_from", [])) or []
    if not isinstance(existing_peers, list):
        raise ValueError("Existing agent_comm allow_from must contain an explicit URN list; wildcard or textual rules are not widened")
    allowed = list(dict.fromkeys(validate_urn(peer) for peer in [*existing_peers, *peers]))
    updates = {"platform_url": helper_url, "urn": urn, "collaboration_enabled": True, "allow_from": allowed}
    if remote:
        updates["remote_enabled"] = True
    # Legacy flat fields win over extra in the connector. Move only fields this
    # command intentionally changes, leaving every unrelated setting intact.
    for key, value in updates.items():
        platform.pop(key, None)
        extra[key] = value
    platform["enabled"] = True
    return result, extra, allowed


def _assert_unmanaged(config):
    if callable(getattr(config, "is_managed", None)) and config.is_managed():
        raise RuntimeError("This Hermes configuration is managed; use its administrator-supported setup path")
    try:
        from hermes_cli.managed_scope import is_key_managed
    except ImportError:
        return
    keys = ["plugins.enabled", "plugins.disabled", "platforms.agent_comm", "platforms.agent_comm.enabled"]
    for field in ("platform_url", "urn", "collaboration_enabled", "remote_enabled", "allow_from"):
        keys.extend([f"platforms.agent_comm.{field}", f"platforms.agent_comm.extra.{field}"])
    if any(is_key_managed(key) for key in keys):
        raise RuntimeError("The relevant Hermes settings are administrator-managed")


def configure(args):
    constants, config = ensure_hermes()
    from agent_comm_runtime.identity import validate_urn
    from agent_comm_runtime.remote import RemoteBridge, hermes_principal, instant
    if args.pair_console and (not args.remote or not args.expires):
        raise ValueError("--pair-console requires --remote and an explicit --expires RFC3339 deadline")
    if args.expires and not args.pair_console:
        raise ValueError("--expires only applies with --pair-console")
    if args.allow_web_actions and not args.pair_console:
        raise ValueError("--allow-web-actions requires an explicit --pair-console grant")
    pair_methods = [*PAIR_METHODS, *(WEB_ACTION_METHODS if args.allow_web_actions else [])]
    peers = [validate_urn(peer) for peer in args.allow_peer]
    if args.pair_console:
        peers.append(validate_urn(args.pair_console))
        if instant(args.expires) <= datetime.now(timezone.utc).timestamp():
            raise ValueError("Remote pairing expiry must be in the future")
    home = Path(constants.get_hermes_home()).expanduser().resolve()
    config_path = Path(config.get_config_path()).expanduser().resolve()
    if config_path != home / "config.yaml":
        raise RuntimeError("Hermes config path does not match the selected native profile; no file was changed")
    _assert_unmanaged(config)
    original = config.require_readable_config_before_write(config_path)
    if not isinstance(original, dict):
        raise ValueError("Hermes configuration must be a mapping")
    before = config_path.read_bytes() if config_path.exists() else None
    helper_url, urn = helper_info(args.helper_url)
    merged, extra, allowed = merge_config(original, helper_url=helper_url, urn=urn, peers=peers, remote=args.remote)
    platform = merged["platforms"]["agent_comm"]
    remote_enabled = platform.get("remote_enabled", extra.get("remote_enabled")) is True
    plan = {"profile": str(home), "config": str(config_path), "helper_url": helper_url, "urn": urn,
            "attention_plugin": str(home / "plugins" / "agent-comm-attention"),
            "collaboration_enabled": True, "remote_enabled": remote_enabled, "allow_from": allowed,
            "remote_pairing": {"console_urn": args.pair_console, "methods": pair_methods,
                               "expires_at": args.expires} if args.pair_console else None}
    print(json.dumps({"status": "configuration_plan", **plan}, ensure_ascii=False, indent=2))
    if not allowed:
        print("No peer has been allowed. This does not permit messages to arbitrary people; confirm explicit contacts and task grants before collaborating.")
    if remote_enabled and not args.pair_console:
        print("Remote mode does not pair or trust a Web console. Pair an explicit console locally when you choose to grant access.")
    if args.check_only:
        print("Check only: no configuration, backup, or pairing was written.")
        return plan
    if args.pair_console:
        # Finish registration before writing a grant. A failed platform request
        # leaves the previous configuration and all local data untouched.
        ensure_platform_registration(helper_url, urn)
    install_attention_companion(home)
    home.mkdir(parents=True, exist_ok=True)
    if (config_path.read_bytes() if config_path.exists() else None) != before:
        raise RuntimeError("Hermes configuration changed during setup; rerun so the new settings can be merged safely")
    backup = None
    if before is not None:
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        backup = home / ("config.yaml.agent-comm-backup-" + suffix)
        # Exclusive creation: never overwrite an earlier recovery copy.
        with backup.open("xb") as stream:
            stream.write(before)
        shutil.copymode(config_path, backup)
    config.atomic_config_write(config_path, merged)
    if args.pair_console:
        remote_path = platform.get("remote_state_path", extra.get("remote_state_path")) or home / "agent-comm" / "remote.sqlite3"
        try:
            bridge = RemoteBridge(remote_path, None, urn, bound_principal=hermes_principal(home))
            try:
                bridge.pair(args.pair_console, hermes_principal(home), pair_methods, args.expires)
            finally:
                bridge.close()
        except Exception as exc:
            raise RuntimeError(f"Configuration was saved at {config_path} (backup: {backup}), but local pairing could not be confirmed; inspect the local pairing state before retrying") from exc
    print(json.dumps({"status": "configured", "config": str(config_path), "backup": str(backup) if backup else None,
                      "paired_console": args.pair_console}, ensure_ascii=False))
    print("Restart Hermes Gateway and dashboard using their normal controls; reload Desktop to show Agent Comm attention. Keys, mailboxes and existing collaboration data were retained.")
    return plan


def main(argv=None):
    utf8_output()
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--helper-url", default="http://127.0.0.1:45042")
    cli.add_argument("--allow-peer", action="append", default=[], help="Explicit peer URN; repeat as needed. '*' is rejected")
    cli.add_argument("--remote", action="store_true", help="Enable the paired remote RPC processor; does not itself trust a console")
    cli.add_argument("--pair-console", help="Explicit local permission for this console to read state and converse with this Hermes profile")
    cli.add_argument("--allow-web-actions", action="store_true", help="Also permit friend requests, messages, read state and collaboration approval actions")
    cli.add_argument("--expires", help="Required RFC3339 expiry for --pair-console")
    cli.add_argument("--check-only", action="store_true", help="Read helper and show the exact configuration/pairing plan without writing")
    args = cli.parse_args(argv)
    try:
        configure(args)
        return 0
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        print(f"Configuration stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
