"""Public HTTP retrieval with DNS pinning, redirect validation and bounded bodies."""

from __future__ import annotations

import asyncio
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import certifi
import httpx


def public_url(value: str) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode("ascii")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid public URL.") from exc
    if (
        parsed.scheme not in {"https", "http"}
        or not host
        or parsed.username
        or parsed.password
        or port not in {80, 443}
        or len(value) > 2000
        or any(ord(c) < 33 for c in value)
        or "\\" in value
    ):
        raise ValueError("Use an HTTP(S) URL without credentials and with a standard port.")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private and local destinations are blocked.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        not address.is_global or address.is_multicast or address.is_reserved
    ):
        raise ValueError("Private and local destinations are blocked.")
    return parsed.scheme, host, port


def fallback_addresses(host: str) -> set[str]:
    """Fixed TLS-verified resolver only when the OS resolver fails; no redirects."""
    addresses = set()
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
        for record_type in ("A", "AAAA"):
            with client.stream(
                "GET",
                "https://1.1.1.1/dns-query",
                params={"name": host, "type": record_type},
                headers={"Accept": "application/dns-json"},
            ) as response:
                response.raise_for_status()
                body = bytearray()
                for part in response.iter_bytes():
                    body.extend(part)
                    if len(body) > 32000:
                        raise ValueError("DNS response exceeds the size limit.")
                import json

                value = json.loads(body)
            if not isinstance(value, dict) or value.get("Status") != 0:
                raise ValueError("The public resolver could not resolve this host.")
            for answer in value.get("Answer", []):
                if answer.get("type") in {1, 28}:
                    addresses.add(str(ipaddress.ip_address(answer["data"])))
    return addresses


def resolve_public(host: str, port: int) -> str:
    try:
        addresses = {
            str(item[4][0]) for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except OSError:
        try:
            addresses = fallback_addresses(host)
        except (OSError, httpx.HTTPError, ValueError, KeyError, TypeError) as fallback:
            raise ValueError(
                "The public host could not be resolved by the system or fallback resolver. Check connectivity or attach a captured source."
            ) from fallback
    if not addresses or any(
        not ipaddress.ip_address(address).is_global
        or ipaddress.ip_address(address).is_multicast
        or ipaddress.ip_address(address).is_reserved
        for address in addresses
    ):
        raise ValueError("The destination resolves to a private or nonpublic address.")
    return sorted(addresses)[0]


def fetch_public(
    url: str,
    *,
    limit: int = 2_000_000,
    headers: dict | None = None,
    allowed_host: str | None = None,
    url_guard=None,
) -> dict:
    """Connect to the validated IP, preserving hostname TLS verification and Host."""
    current = url
    for _ in range(5):
        scheme, host, port = public_url(current)
        if url_guard is not None and not url_guard(current):
            raise ValueError("The destination is disallowed by website access rules.")
        if allowed_host and host != allowed_host:
            raise ValueError("Redirect leaves the permitted host.")
        address = resolve_public(host, port)
        connection = http.client.HTTPConnection(host, port, timeout=12)
        raw_socket = socket.create_connection((address, port), timeout=12)
        try:
            connection.sock = (
                ssl.create_default_context(cafile=certifi.where()).wrap_socket(
                    raw_socket, server_hostname=host
                )
                if scheme == "https"
                else raw_socket
            )
            parsed = urlsplit(current)
            request_headers = {
                "Host": host,
                "User-Agent": "Rilo/2.0 (+local evidence capture)",
                "Accept-Encoding": "identity",
                **(headers or {}),
            }
            connection.request(
                "GET",
                urlunsplit(("", "", parsed.path or "/", parsed.query, "")),
                headers=request_headers,
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                destination = response.getheader("Location")
                if not destination:
                    raise ValueError("Redirect has no destination.")
                current = urljoin(current, destination)
                # Credentials may only be used for fixed, same-host API requests.
                if headers and not allowed_host:
                    headers = None
                continue
            if response.getheader("Content-Encoding", "identity") not in {"identity", ""}:
                raise ValueError("Compressed responses are not accepted by this bounded fetcher.")
            data = bytearray()
            started = time.monotonic()
            while part := response.read(min(65536, limit + 1 - len(data))):
                data.extend(part)
                if len(data) > limit:
                    raise ValueError(
                        f"Source download exceeds the size limit of {limit:,} bytes. Use a smaller source or a bounded repository ZIP."
                    )
                if time.monotonic() - started > 25:
                    raise ValueError(
                        "Source download exceeded 25 seconds. Retry source capture or use a smaller source."
                    )
            return {
                "url": current,
                "status": response.status,
                "headers": dict(response.getheaders()),
                "body": bytes(data),
                "dns_policy": "system resolver; fixed Cloudflare DNS-over-HTTPS fallback on resolution failure; public IP validation and connection pinning",
            }
        except (OSError, http.client.HTTPException) as exc:
            raise ValueError(f"Public retrieval failed ({type(exc).__name__}).") from exc
        finally:
            connection.close()
            raw_socket.close()
    raise ValueError("Too many redirects.")


async def fetch(url: str, **kwargs) -> dict:
    return await asyncio.to_thread(fetch_public, url, **kwargs)
