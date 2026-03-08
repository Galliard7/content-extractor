"""Security gate — URL validation with DNS resolution and private IP blocking."""

import ipaddress
import socket
from urllib.parse import urlparse


def validate_url(url):
    """Validate a URL for safe fetching.

    Returns dict: {"allowed": bool, "reason": str|None, "resolved_ip": str|None}
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return {"allowed": False, "reason": f"Invalid URL: {e}", "resolved_ip": None}

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        return {
            "allowed": False,
            "reason": f"Blocked scheme: {parsed.scheme}",
            "resolved_ip": None,
        }

    hostname = parsed.hostname
    if not hostname:
        return {"allowed": False, "reason": "No hostname", "resolved_ip": None}

    # Block localhost variants
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return {
            "allowed": False,
            "reason": f"Blocked hostname: {hostname}",
            "resolved_ip": None,
        }

    # Block .local domains
    if hostname.endswith(".local"):
        return {
            "allowed": False,
            "reason": f"Blocked .local domain: {hostname}",
            "resolved_ip": None,
        }

    # DNS resolution + private IP check
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if results:
            ip_str = results[0][4][0]
            try:
                addr = ipaddress.ip_address(ip_str)
                if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                    return {
                        "allowed": False,
                        "reason": f"Blocked private IP: {ip_str}",
                        "resolved_ip": ip_str,
                    }
            except ValueError:
                pass
            return {"allowed": True, "reason": None, "resolved_ip": ip_str}
    except socket.gaierror:
        # DNS resolution failed — still allow (might be transient)
        pass

    return {"allowed": True, "reason": None, "resolved_ip": None}
