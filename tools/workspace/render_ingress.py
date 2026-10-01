"""Render the optional production ingress after validating its domains and TLS files.

Only explicit @@NAME@@ placeholders are replaced. Nginx $variables are preserved.
The checked-in PSL is shared with the Gateway, so this command never fetches DNS/PSL.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace-gateway"))
from workspace_gateway.domains import registrable_domain


def load_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not match:
            raise ValueError(f"Unsupported environment syntax at line {number}")
        key, value = match.groups()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed environment quote at line {number}")
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        values[key] = value
    values.update(os.environ)
    return values


def required(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def hostname(value: str) -> str:
    if value != value.lower() or len(value) > 253 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in value.split(".")
    ):
        raise ValueError("Production hostnames must be canonical lowercase DNS names without ports")
    return value


def https_origin(value: str) -> str:
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid HTTPS origin port") from exc
    if (
        parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or port not in {None, 443}
        or not parsed.hostname
    ):
        raise ValueError("Production URLs must be HTTPS origins on port 443")
    return hostname(parsed.hostname)


def validate_settings(values: dict[str, str]) -> dict[str, str]:
    domain = hostname(required(values, "WORKSPACE_GATEWAY_DOMAIN"))
    control = hostname(required(values, "WORKSPACE_GATEWAY_CONTROL_HOST"))
    public_url = required(values, "WORKSPACE_GATEWAY_PUBLIC_URL")
    if https_origin(public_url) != control or public_url not in {"https://" + control, "https://" + control + "/"}:
        raise ValueError("WORKSPACE_GATEWAY_PUBLIC_URL must match WORKSPACE_GATEWAY_CONTROL_HOST")
    portal = https_origin(required(values, "NEXTAUTH_URL"))
    node_site, control_site, portal_site = map(registrable_domain, (domain, control, portal))
    if node_site != control_site or node_site == portal_site:
        raise ValueError("Control and node domains must share a registrable workspace site separate from the portal")
    if re.fullmatch(r"[a-f0-9]{24}\." + re.escape(domain), control):
        raise ValueError("The connector hostname cannot also be a node hostname")
    secret = required(values, "WORKSPACE_GATEWAY_SECRET")
    if len(secret) < 32 or secret == values.get("NEXTAUTH_SECRET") or "replace-with" in secret:
        raise ValueError("Set an independent Workspace Gateway secret of at least 32 characters")
    subnet = ipaddress.ip_network(values.get("WORKSPACE_INGRESS_SUBNET", "172.30.80.0/29"), strict=True)
    nginx_ip = ipaddress.ip_address(values.get("WORKSPACE_INGRESS_NGINX_IP", "172.30.80.2"))
    gateway_ip = ipaddress.ip_address(values.get("WORKSPACE_INGRESS_GATEWAY_IP", "172.30.80.3"))
    private_subnet = subnet.version == 4 and any(
        subnet.subnet_of(ipaddress.ip_network(block)) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    )
    if (
        not private_subnet or subnet.prefixlen < 24 or subnet.prefixlen > 29
        or nginx_ip not in subnet or gateway_ip not in subnet or nginx_ip == gateway_ip
        or nginx_ip in {subnet.network_address, subnet.broadcast_address}
        or gateway_ip in {subnet.network_address, subnet.broadcast_address}
    ):
        raise ValueError("Use distinct usable IPv4 addresses in a private /24 to /29 ingress network")
    body_limit = int(values.get("WORKSPACE_GATEWAY_HTTP_LIMIT", "2097152"))
    if not 1024 <= body_limit <= 16 * 1024 * 1024:
        raise ValueError("WORKSPACE_GATEWAY_HTTP_LIMIT must be between 1 KiB and 16 MiB")
    return {
        "CONTROL_HOST": control, "NODE_DOMAIN_REGEX": re.escape(domain),
        "NGINX_IP": str(nginx_ip), "HTTP_BODY_LIMIT": str(body_limit), "NODE_DOMAIN": domain,
    }


def openssl_run(binary: str, *args: str, input_data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run([binary, *args], input=input_data, capture_output=True, check=False, timeout=15)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("OpenSSL certificate check timed out") from exc
    if result.returncode:
        # Never include raw command output: private paths or sensitive key errors may be present.
        raise ValueError("OpenSSL could not validate a certificate or key")
    return result.stdout


def validate_certificate(directory: Path, expected_name: str, binary: str, *, wildcard: bool = False) -> None:
    directory = directory.resolve(strict=True)
    cert = directory / "fullchain.pem"
    key = directory / "privkey.pem"
    for path in (cert, key):
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(directory) or not resolved.is_file():
            raise ValueError("Certificate files must stay inside their mounted directory; flatten external symlinks")
    openssl_run(binary, "x509", "-in", str(cert), "-noout", "-checkend", "86400")
    sans = openssl_run(binary, "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName").decode("ascii")
    names = {name.lower() for name in re.findall(r"DNS:([^,\s]+)", sans)}
    if wildcard:
        covered = "*." + expected_name in names
    else:
        labels = expected_name.split(".")
        covered = expected_name in names or (len(labels) > 2 and "*." + ".".join(labels[1:]) in names)
    if not covered:
        raise ValueError("Certificate SAN does not cover the configured control hostname or node wildcard")
    public = openssl_run(binary, "x509", "-in", str(cert), "-pubkey", "-noout")
    cert_key = openssl_run(binary, "pkey", "-pubin", "-outform", "DER", input_data=public)
    private_key = openssl_run(binary, "pkey", "-in", str(key), "-passin", "pass:", "-pubout", "-outform", "DER")
    if cert_key != private_key:
        raise ValueError("Certificate and private key do not match")


def render(values: dict[str, str], output: Path, binary: str) -> Path:
    settings = validate_settings(values)
    validate_certificate(Path(required(values, "WORKSPACE_CONTROL_CERT_DIR")), settings["CONTROL_HOST"], binary)
    validate_certificate(Path(required(values, "WORKSPACE_NODE_CERT_DIR")), settings["NODE_DOMAIN"], binary, wildcard=True)
    rendered: list[tuple[str, str]] = []
    for name in ("workspace.conf", "workspace-proxy.inc"):
        source = (ROOT / "deploy" / "nginx" / (name + ".template")).read_text(encoding="utf-8")
        for key, value in settings.items():
            source = source.replace("@@" + key + "@@", value)
        if "@@" in source:
            raise ValueError("Unresolved template placeholder")
        rendered.append((name, source))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name, content in rendered:
        temporary = output / (name + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(output / name)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path, help="Rendered config directory; defaults to WORKSPACE_NGINX_CONFIG_DIR")
    parser.add_argument("--openssl", default=shutil.which("openssl"), help="OpenSSL executable for SAN/key/expiry checks")
    args = parser.parse_args()
    try:
        if not args.openssl:
            raise ValueError("OpenSSL is required; provide its executable with --openssl")
        values = load_environment(args.env_file)
        output = args.output or Path(required(values, "WORKSPACE_NGINX_CONFIG_DIR"))
        print(f"Validated Workspace Gateway ingress: {render(values, output, args.openssl)}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Workspace ingress refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
