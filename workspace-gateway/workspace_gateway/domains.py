"""Offline ICANN + PRIVATE Public Suffix List validation (standard library only)."""
import ipaddress
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit


def normalize_hostname(host):
    if not isinstance(host, str) or not host or len(host) > 253 or host != host.strip():
        raise ValueError("Invalid hostname")
    host = host.rstrip(".").lower()
    if any(c in host for c in "/:@?#\\\\"):
        raise ValueError("Invalid hostname")
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("Invalid IDNA hostname") from exc
    if len(host) > 253 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
        raise ValueError("Invalid DNS hostname")
    return host


@lru_cache(maxsize=1)
def suffix_rules():
    path = Path(__file__).with_name("public_suffix_list.dat")
    if not path.is_file():
        raise ValueError("Vendored public suffix list is missing")
    rules = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        prefix = "!" if line.startswith("!") else "*." if line.startswith("*.") else ""
        rules.add(prefix + normalize_hostname(line[len(prefix):]))
    return frozenset(rules)


def registrable_domain(host):
    host = normalize_hostname(host)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Production origins must use DNS hostnames")
    labels = host.split(".")
    if len(labels) < 2 or any(not label or len(label) > 63 for label in labels):
        raise ValueError("Invalid production hostname")
    rules = suffix_rules()
    matches = []
    for index in range(len(labels)):
        candidate = ".".join(labels[index:])
        if "!" + candidate in rules:
            return candidate
        if candidate in rules:
            matches.append(len(labels) - index)
        if index and "*." + candidate in rules:
            matches.append(len(labels) - index + 1)
    if not matches or len(labels) <= max(matches):
        raise ValueError("Hostname has an unknown suffix or is itself a public suffix")
    return ".".join(labels[-max(matches)-1:])


def validate_origins(domain, scheme, control_host, portal_origin):
    if scheme == "http":
        if domain.split(":")[0] != "localhost":
            raise ValueError("HTTP is only available for localhost development")
        return
    portal = urlsplit(portal_origin)
    if (portal.scheme != "https" or not portal.hostname or portal.username or portal.password
            or portal.path not in {"", "/"} or portal.query or portal.fragment):
        raise ValueError("Production requires WORKSPACE_GATEWAY_PORTAL_ORIGIN as an HTTPS origin")
    workspace = registrable_domain(domain.split(":")[0])
    control = registrable_domain(control_host.split(":")[0])
    if workspace != control:
        raise ValueError("Workspace and control hosts must use the same registrable domain")
    if workspace == registrable_domain(portal.hostname):
        raise ValueError("Workspace/control and portal require separate registrable domains")
