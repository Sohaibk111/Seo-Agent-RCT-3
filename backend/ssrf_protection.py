import socket
import ipaddress
from urllib.parse import urlparse
from typing import List, Set
from backend.exceptions import ValidationErrorException
from backend.logging_config import logger

# Forbidden IP Networks (IPv4 and IPv6)
BLOCKED_IP_NETWORKS: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network (only valid as source)
    ipaddress.ip_network("10.0.0.0/8"),         # Private IPv4
    ipaddress.ip_network("100.64.0.0/10"),      # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback IPv4
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local & Cloud Metadata Services (AWS, GCP, Azure)
    ipaddress.ip_network("172.16.0.0/12"),      # Private IPv4
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay
    ipaddress.ip_network("192.168.0.0/16"),     # Private IPv4
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmark
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast IPv4
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved IPv4
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast IPv4
    
    ipaddress.ip_network("::/128"),             # Unspecified IPv6
    ipaddress.ip_network("::1/128"),            # Loopback IPv6
    ipaddress.ip_network("fc00::/7"),           # Unique Local IPv6
    ipaddress.ip_network("fe80::/10"),          # Link-Local IPv6
    ipaddress.ip_network("::ffff:0:0/96"),      # IPv4-mapped IPv6
]

# Explicitly forbidden hostnames
BLOCKED_HOSTNAMES: Set[str] = {
    "localhost",
    "loopback",
    "metadata.google.internal",
    "169.254.169.254",
    "kubernetes.default.svc",
    "kubernetes.default",
    "host.docker.internal",
}

def is_ip_blocked(ip_str: str) -> bool:
    """Checks whether an IP address belongs to any forbidden internal/private network."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        # Check if private, loopback, link_local, or reserved
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified:
            return True
            
        # Explicit check against CIDR network list
        for network in BLOCKED_IP_NETWORKS:
            if ip_obj in network:
                return True
        return False
    except ValueError:
        return True

def validate_url_ssrf(url: str) -> str:
    """
    Validates a target URL against Server-Side Request Forgery (SSRF) attack vectors.
    - Scheme must be strictly 'http' or 'https'
    - Hostname must not match internal metadata or loopback names
    - DNS resolution is performed and all resolved IPs are verified against internal/private CIDRs.
    Raises ValidationErrorException if the URL violates SSRF safety constraints.
    """
    if not url or not isinstance(url, str):
        raise ValidationErrorException(message="SSRF Protection: Invalid URL provided.")

    clean_url = url.strip()
    parsed = urlparse(clean_url)

    # 1. Scheme Check
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValidationErrorException(
            message=f"SSRF Protection: Forbidden URL scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed."
        )

    # 2. Hostname Check
    hostname = parsed.hostname
    if not hostname:
        raise ValidationErrorException(message="SSRF Protection: Unable to parse valid hostname from URL.")

    clean_hostname = hostname.lower().strip()

    if clean_hostname in BLOCKED_HOSTNAMES or clean_hostname.endswith(".local") or clean_hostname.endswith(".internal"):
        raise ValidationErrorException(
            message=f"SSRF Protection: Access to internal host '{clean_hostname}' is strictly blocked."
        )

    # 3. Direct IP Check
    try:
        ip_obj = ipaddress.ip_address(clean_hostname)
        if is_ip_blocked(str(ip_obj)):
            raise ValidationErrorException(
                message=f"SSRF Protection: Access to IP address '{clean_hostname}' is restricted."
            )
        return clean_url
    except ValueError:
        # Hostname is a domain name, proceed to DNS resolution
        pass

    # 4. DNS Resolution & IP Check
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(clean_hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            raise ValidationErrorException(message=f"SSRF Protection: Unable to resolve hostname '{clean_hostname}'.")

        resolved_ips = set()
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_addr = sockaddr[0]
            resolved_ips.add(ip_addr)

        for ip_addr in resolved_ips:
            if is_ip_blocked(ip_addr):
                logger.warning(f"SSRF Blocked: Domain '{clean_hostname}' resolved to restricted IP '{ip_addr}'")
                raise ValidationErrorException(
                    message=f"SSRF Protection: Domain '{clean_hostname}' resolves to restricted IP address '{ip_addr}'."
                )

    except socket.gaierror as e:
        logger.warning(f"SSRF Protection: DNS lookup failed for '{clean_hostname}': {e}")
        raise ValidationErrorException(message=f"SSRF Protection: Could not resolve hostname '{clean_hostname}'.")

    return clean_url
