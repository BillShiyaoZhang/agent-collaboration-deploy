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


ORIGIN_MODES = {"separate-site", "same-site-subdomains"}


def validate_origins(domain, scheme, control_host, portal_origin, origin_mode="separate-site"):
    if not isinstance(origin_mode, str) or origin_mode not in ORIGIN_MODES:
        raise ValueError("Unknown workspace origin mode")
    if scheme == "http":
        if origin_mode != "separate-site":
            raise ValueError("Same-site subdomains require HTTPS")
        if domain.split(":")[0] != "localhost":
            raise ValueError("HTTP is only available for localhost development")
        return
    if scheme != "https":
        raise ValueError("Workspace origins require HTTPS")
    portal = urlsplit(portal_origin)
    if (portal.scheme != "https" or not portal.hostname or portal.username or portal.password
            or portal.path not in {"", "/"} or portal.query or portal.fragment):
        raise ValueError("Production requires WORKSPACE_GATEWAY_PORTAL_ORIGIN as an HTTPS origin")
    node_host = normalize_hostname(domain.split(":")[0])
    connector_host = normalize_hostname(control_host.split(":")[0])
    portal_host = normalize_hostname(portal.hostname)
    workspace = registrable_domain(node_host)
    control = registrable_domain(connector_host)
    if workspace != control:
        raise ValueError("Workspace and control hosts must use the same registrable domain")
    if re.fullmatch(r"[a-f0-9]{24}\." + re.escape(node_host), connector_host):
        raise ValueError("The connector hostname cannot also be a node hostname")
    if (portal_host == connector_host or portal_host == node_host
            or portal_host.endswith("." + node_host)):
        raise ValueError("Portal must use a different host outside the node domain")
    portal_site = registrable_domain(portal_host)
    if origin_mode == "separate-site" and workspace == portal_site:
        raise ValueError("Workspace/control and portal require separate registrable domains")
    if origin_mode == "same-site-subdomains" and workspace != portal_site:
        raise ValueError("Same-site subdomains must share the portal registrable domain")
