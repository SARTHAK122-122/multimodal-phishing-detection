"""SSRF-safe URL validation shared by every modality that touches the network.

Website scans fetch pages, email/SMS/QR scans analyse extracted links. All of
them run untrusted input through :func:`validate_url_for_fetch` **before** any
socket is opened, and every redirect hop is re-validated with the same rules.

Threat model
------------
A malicious user submits ``http://169.254.169.254/latest/meta-data/`` (cloud
metadata), ``http://localhost:8088/api/health`` (internal service),
``http://[::1]/``, or a public URL that 302-redirects to an internal address.
The goal of this module is to make all of those impossible to reach.

Defence layers
--------------
1. Scheme allow-list (http/https only; ``file:``, ``ftp:``, ``javascript:``,
   ``data:`` rejected).
2. No credentials in the authority (``user:pass@host``) - they confuse both
   the parser and the destination host.
3. Port allow-list (80/443/8080/8443 + explicit opt-in) so ``http://host:22``
   or ``:6379`` (Redis) cannot be probed.
4. Literal-IP hosts checked directly; named hosts resolved with DNS and **all**
   resolved addresses checked (an attacker controlling DNS can mix a public A
   record with a private one).
5. Every resolved address tested against loopback, RFC1918, link-local,
   CGNAT, multicast, reserved, and the cloud-metadata link-local range.

DNS rebinding note: we resolve and validate immediately before connecting and
re-validate on every redirect. Fully pinning the connection to the validated IP
would require speaking HTTP over a raw socket; for this project the
resolve-then-fetch-in-one-step approach is documented as the accepted residual
risk (an attacker would have to win a sub-millisecond DNS race on both the
initial hop and each redirect).
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

# Schemes the fetcher will ever open.
ALLOWED_SCHEMES = {"http", "https"}

# Ports considered safe to connect to for a *webpage*. Anything else is
# rejected so the scanner cannot be turned into an internal port prober.
DEFAULT_ALLOWED_PORTS = {80, 443, 8080, 8443}

# Maximum length of a submitted URL; longer strings are almost certainly junk
# or a buffer-abuse attempt, not a real webpage.
MAX_URL_LENGTH = 2048


@dataclass
class UrlVerdict:
    """Result of validating one URL for fetching.

    ``safe`` is the only field the caller should branch on for network access.
    ``reason`` is a short machine-ish token (``private_address``), ``detail``
    is human-readable and safe to surface as evidence.
    """

    safe: bool
    normalized: str = ""
    host: str = ""
    scheme: str = ""
    reason: str = ""
    detail: str = ""
    resolved_ips: List[str] = field(default_factory=list)

    def as_evidence(self) -> dict:
        return {
            "safe": self.safe,
            "reason": self.reason,
            "detail": self.detail,
            "host": self.host,
            "resolvedIps": self.resolved_ips,
        }


def _deny(reason: str, detail: str, **kw) -> UrlVerdict:
    return UrlVerdict(safe=False, reason=reason, detail=detail, **kw)


def _blocked_ip(ip: ipaddress._BaseAddress) -> Tuple[bool, str]:
    """Return (blocked, reason) for a single resolved address."""
    checks = (
        ("loopback_address", ip.is_loopback),
        ("private_address", ip.is_private),
        ("link_local_address", ip.is_link_local),
        ("multicast_address", ip.is_multicast),
        ("reserved_address", ip.is_reserved),
        ("unspecified_address", ip.is_unspecified),
    )
    for reason, flag in checks:
        if flag:
            return True, reason

    # CGNAT 100.64.0.0/10 is not covered by is_private on all Python versions.
    if isinstance(ip, ipaddress.IPv4Address):
        if ip in ipaddress.ip_network("100.64.0.0/10"):
            return True, "cgnat_address"
        # 169.254.169.254 and friends: the whole link-local /16 is already
        # caught above; this keeps the cloud-metadata intent explicit.
        if ip in ipaddress.ip_network("169.254.0.0/16"):
            return True, "cloud_metadata_address"
    return False, ""


def resolve_host(host: str, port: int) -> Tuple[Optional[List[str]], str]:
    """Resolve ``host`` to every A/AAAA address.

    Returns ``(ips, error_reason)``. ``ips`` is ``None`` on failure. All
    addresses are returned so a mixed public/private answer is fully checked.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError) as exc:
        return None, f"dns_resolution_failed ({exc.__class__.__name__})"

    ips: List[str] = []
    for info in infos:
        addr = info[4][0]
        if addr not in ips:
            ips.append(addr)
    if not ips:
        return None, "dns_resolution_failed (no addresses)"
    return ips, ""


def validate_url_for_fetch(
    raw_url: str,
    *,
    allowed_ports: Optional[set] = None,
    resolve_dns: bool = True,
) -> UrlVerdict:
    """Validate an untrusted URL for safe fetching.

    Never raises. Returns a :class:`UrlVerdict`; ``safe`` is ``True`` only when
    every check passes. When ``resolve_dns`` is false the DNS check is skipped
    (used for pure link *characteristics* analysis where no connection is made,
    e.g. scoring an SMS link we will not visit).
    """
    if not isinstance(raw_url, str) or not raw_url.strip():
        return _deny("empty_url", "No URL was provided.")

    url = raw_url.strip()
    if len(url) > MAX_URL_LENGTH:
        return _deny("url_too_long", f"URL exceeds {MAX_URL_LENGTH} characters.")

    try:
        parts = urlsplit(url)
    except ValueError as exc:
        return _deny("unparsable_url", f"The URL could not be parsed: {exc}")

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        return _deny(
            "unsupported_scheme",
            f"Only http:// and https:// URLs may be analysed (got '{scheme or 'none'}').",
            scheme=scheme,
        )

    host = (parts.hostname or "").lower()
    if not host:
        return _deny("missing_host", "The URL has no hostname.")

    # Credentials in the authority are a classic trick to make
    # "https://google.com@evil.example/" look trustworthy.
    if parts.username or parts.password:
        return _deny(
            "credentials_in_url",
            "The URL embeds credentials (user:pass@host); this is a phishing pattern "
            "and is refused for fetching.",
            host=host,
            scheme=scheme,
        )

    ports = allowed_ports or DEFAULT_ALLOWED_PORTS
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError:
        return _deny("invalid_port", "The URL specifies an invalid port.", host=host)
    if port not in ports:
        return _deny(
            "disallowed_port",
            f"Port {port} is not an allowed web port ({sorted(ports)}).",
            host=host,
            scheme=scheme,
        )

    normalized = urlunsplit((scheme, parts.netloc.lower(), parts.path or "/", parts.query, ""))

    # Literal IP in the host part?
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None

    resolved: List[str] = []
    if ip is not None:
        blocked, reason = _blocked_ip(ip)
        if blocked:
            return _deny(
                reason,
                f"The host resolves to a {reason.replace('_', ' ')}, which is never fetched.",
                host=host,
                scheme=scheme,
            )
        resolved = [str(ip)]
    elif resolve_dns:
        ips, err = resolve_host(host, port)
        if ips is None:
            return _deny(err, "The hostname could not be resolved.", host=host, scheme=scheme)
        for addr in ips:
            try:
                resolved_ip = ipaddress.ip_address(addr)
            except ValueError:
                return _deny("unparsable_address", f"DNS returned an unparsable address.", host=host)
            blocked, reason = _blocked_ip(resolved_ip)
            if blocked:
                return _deny(
                    reason,
                    f"'{host}' resolves to {addr}, a {reason.replace('_', ' ')}. "
                    "Internal addresses are never fetched.",
                    host=host,
                    scheme=scheme,
                    resolved_ips=ips,
                )
        resolved = ips

    return UrlVerdict(
        safe=True,
        normalized=normalized,
        host=host,
        scheme=scheme,
        resolved_ips=resolved,
        detail="Passed scheme, credential, port and address-range checks.",
    )


def is_safe(raw_url: str, **kw) -> bool:
    return validate_url_for_fetch(raw_url, **kw).safe
