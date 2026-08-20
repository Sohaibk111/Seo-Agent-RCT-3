import axios from 'axios';
import http from 'http';
import https from 'https';
import dns from 'dns';

export interface RedirectHop {
  url: string;
  status_code: number;
  location?: string;
}

export interface FetchOptions {
  timeoutMs?: number;
  allowLocalIp?: boolean;
  maxBytes?: number;
  maxRedirects?: number;
}

export interface FetchResult {
  url: string;
  status_code: number;
  redirects: RedirectHop[];
  headers: Record<string, string>;
  response_time: number; // in milliseconds
  html: string;
  content_type?: string;
  error?: string;
}

/**
 * Checks if an IPv4 address is in a private, loopback, link-local, or reserved range.
 */
export function isPrivateOrReservedIPv4(ip: string): boolean {
  // Normalize dotted-decimal IP
  const parts = ip.split('.').map(p => parseInt(p, 10));
  if (parts.length !== 4 || parts.some(p => isNaN(p) || p < 0 || p > 255)) {
    return false;
  }

  const [b0, b1, b2] = parts;

  // 0.0.0.0/8 (Current network)
  if (b0 === 0) return true;

  // 127.0.0.0/8 (Loopback)
  if (b0 === 127) return true;

  // 10.0.0.0/8 (Private)
  if (b0 === 10) return true;

  // 172.16.0.0/12 (Private: 172.16.0.0 - 172.31.255.255)
  if (b0 === 172 && b1 >= 16 && b1 <= 31) return true;

  // 192.168.0.0/16 (Private)
  if (b0 === 192 && b1 === 168) return true;

  // 169.254.0.0/16 (Link-local / Cloud Metadata)
  if (b0 === 169 && b1 === 254) return true;

  // 100.64.0.0/10 (Carrier-grade NAT: 100.64.0.0 - 100.127.255.255)
  if (b0 === 100 && b1 >= 64 && b1 <= 127) return true;

  // 192.0.0.0/24 (IETF Protocol Assignments)
  if (b0 === 192 && b1 === 0 && b2 === 0) return true;

  // 192.0.2.0/24 (TEST-NET-1)
  if (b0 === 192 && b1 === 0 && b2 === 2) return true;

  // 198.51.100.0/24 (TEST-NET-2)
  if (b0 === 198 && b1 === 51 && b2 === 100) return true;

  // 203.0.113.0/24 (TEST-NET-3)
  if (b0 === 203 && b1 === 0 && b2 === 113) return true;

  // 198.18.0.0/15 (Benchmarking: 198.18.0.0 - 198.19.255.255)
  if (b0 === 198 && (b1 === 18 || b1 === 19)) return true;

  // 224.0.0.0/4 (Multicast: 224.0.0.0 - 239.255.255.255)
  if (b0 >= 224 && b0 <= 239) return true;

  // 240.0.0.0/4 (Reserved / Future use & Broadcast 255.255.255.255)
  if (b0 >= 240) return true;

  return false;
}

/**
 * Checks if an IPv6 address is in a private, loopback, link-local, or reserved range.
 */
export function isPrivateOrReservedIPv6(ip: string): boolean {
  const clean = ip.toLowerCase().replace(/^\[|\]$/g, '');
  if (
    clean === '::1' ||
    clean === '::' ||
    clean === '0:0:0:0:0:0:0:1' ||
    clean === '0:0:0:0:0:0:0:0'
  ) {
    return true;
  }

  // Unique local addresses (fc00::/7 -> fc.. or fd..)
  if (clean.startsWith('fc') || clean.startsWith('fd')) {
    return true;
  }

  // Link-local addresses (fe80::/10 -> fe8, fe9, fea, feb)
  if (
    clean.startsWith('fe8') ||
    clean.startsWith('fe9') ||
    clean.startsWith('fea') ||
    clean.startsWith('feb')
  ) {
    return true;
  }

  // Multicast (ff00::/8)
  if (clean.startsWith('ff')) {
    return true;
  }

  // IPv4-mapped IPv6 (::ffff:x.x.x.x)
  if (clean.includes('::ffff:')) {
    const ipv4Part = clean.split('::ffff:')[1];
    if (ipv4Part && ipv4Part.includes('.')) {
      return isPrivateOrReservedIPv4(ipv4Part);
    }
    return true;
  }

  return false;
}

/**
 * Validates whether a URL is safe from SSRF vulnerabilities and protocol abuse.
 */
export function validateSafeUrl(rawUrl: string, allowLocalIp: boolean = false): { safe: boolean; reason?: string } {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return { safe: false, reason: 'Invalid URL format' };
  }

  // Protocol check: only http and https allowed
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { safe: false, reason: `Disallowed protocol: ${parsed.protocol}. Only http: and https: are allowed.` };
  }

  // Reject credentials in URL
  if (parsed.username || parsed.password) {
    return { safe: false, reason: 'Userinfo (username/password) in URL is disallowed' };
  }

  const hostname = parsed.hostname.toLowerCase();

  // Block cloud metadata hostnames
  const cloudMetadataHosts = [
    'metadata.google.internal',
    'metadata.goog',
    '169.254.169.254',
    'instance-data',
    'metadata',
    'wpad'
  ];
  if (cloudMetadataHosts.includes(hostname) || hostname.endsWith('.metadata.google.internal')) {
    return { safe: false, reason: `Blocked access to cloud metadata host: ${hostname}` };
  }

  // If local IPs are explicitly allowed (e.g. inside explicit local testing environment)
  if (allowLocalIp) {
    return { safe: true };
  }

  // Block localhost and loopback domain variants
  if (
    hostname === 'localhost' ||
    hostname.endsWith('.localhost') ||
    hostname === '0.0.0.0' ||
    hostname === '127.0.0.1' ||
    hostname === '::1' ||
    hostname === '[::1]' ||
    hostname === '0'
  ) {
    return { safe: false, reason: `Blocked localhost/loopback access: ${hostname}` };
  }

  // Check numeric / decimal / hex IP bypasses
  if (/^0x[0-9a-f]+$/i.test(hostname) || /^\d+$/.test(hostname)) {
    return { safe: false, reason: 'Non-standard integer/hex encoded IP addresses are disallowed' };
  }

  // Check IPv4 addresses
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(hostname)) {
    if (isPrivateOrReservedIPv4(hostname)) {
      return { safe: false, reason: `Blocked private or reserved IPv4 address: ${hostname}` };
    }
  }

  // Check IPv6 addresses (enclosed in brackets or plain)
  if (hostname.includes(':') || hostname.startsWith('[')) {
    if (isPrivateOrReservedIPv6(hostname)) {
      return { safe: false, reason: `Blocked private/loopback IPv6 address: ${hostname}` };
    }
  }

  return { safe: true };
}

/**
 * Resolves a hostname via DNS and checks whether any resolved address points to private or reserved IP space.
 * Prevents DNS rebinding and domain-based SSRF bypasses.
 */
export async function resolveAndValidateDns(
  hostname: string,
  allowLocalIp: boolean = false
): Promise<{ safe: boolean; ips?: string[]; reason?: string }> {
  if (allowLocalIp) {
    return { safe: true };
  }

  const cleanHost = hostname.replace(/^\[|\]$/g, '').trim().toLowerCase();

  // If already an IPv4 or IPv6 literal, validate directly
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(cleanHost)) {
    if (isPrivateOrReservedIPv4(cleanHost)) {
      return { safe: false, reason: `Resolved to blocked private/reserved IPv4 address: ${cleanHost}` };
    }
    return { safe: true, ips: [cleanHost] };
  }

  if (cleanHost.includes(':')) {
    if (isPrivateOrReservedIPv6(cleanHost)) {
      return { safe: false, reason: `Resolved to blocked private/reserved IPv6 address: ${cleanHost}` };
    }
    return { safe: true, ips: [cleanHost] };
  }

  try {
    const addresses = await dns.promises.lookup(cleanHost, { all: true });
    const resolvedIps: string[] = [];

    for (const record of addresses) {
      const ip = record.address;
      resolvedIps.push(ip);

      if (record.family === 4 || ip.includes('.')) {
        if (isPrivateOrReservedIPv4(ip)) {
          return {
            safe: false,
            ips: resolvedIps,
            reason: `DNS rebinding/resolution blocked: domain "${cleanHost}" resolved to private/reserved IP: ${ip}`
          };
        }
      } else if (record.family === 6 || ip.includes(':')) {
        if (isPrivateOrReservedIPv6(ip)) {
          return {
            safe: false,
            ips: resolvedIps,
            reason: `DNS rebinding/resolution blocked: domain "${cleanHost}" resolved to private/reserved IPv6: ${ip}`
          };
        }
      }
    }

    return { safe: true, ips: resolvedIps };
  } catch (err: any) {
    // If DNS resolution fails with standard lookup errors (e.g. ENOTFOUND)
    return {
      safe: false,
      reason: `DNS resolution failed for hostname "${cleanHost}": ${err.code || err.message}`
    };
  }
}

/**
 * Creates custom safe lookup function for Node HTTP/HTTPS agents to enforce socket-level DNS resolution checks.
 */
export function createSafeDnsLookup(allowLocalIp: boolean = false) {
  return (
    hostname: string,
    options: any,
    callback: (err: NodeJS.ErrnoException | null, address: string | dns.LookupAddress[], family?: number) => void
  ) => {
    const cb = typeof options === 'function' ? options : callback;
    const opts = typeof options === 'function' ? {} : options;

    dns.lookup(hostname, opts, (err, address, family) => {
      if (err) {
        return cb(err, address as any, family);
      }

      if (!allowLocalIp) {
        const addresses = Array.isArray(address)
          ? address
          : [{ address: address as string, family: family as number }];

        for (const item of addresses) {
          const ip = typeof item === 'string' ? item : item?.address;
          if (ip) {
            if (isPrivateOrReservedIPv4(ip) || isPrivateOrReservedIPv6(ip)) {
              return cb(
                new Error(`SSRF Security Violation: DNS resolved to private or reserved IP: ${ip}`) as any,
                address as any,
                family
              );
            }
          }
        }
      }

      cb(null, address as any, family);
    });
  };
}

/**
 * Fetches an HTTP URL and collects status code, redirects, response headers, response time, and HTML content.
 */
export async function fetchUrl(
  targetUrl: string,
  optionsOrTimeout: number | FetchOptions = 10000
): Promise<FetchResult> {
  const options: FetchOptions =
    typeof optionsOrTimeout === 'number'
      ? { timeoutMs: optionsOrTimeout }
      : optionsOrTimeout;

  const timeoutMs = options.timeoutMs ?? 10000;
  const allowLocalIp = options.allowLocalIp === true;
  const maxBytes = options.maxBytes ?? 10 * 1024 * 1024; // 10MB default
  const maxRedirects = options.maxRedirects ?? 5;

  const startTime = Date.now();
  const redirects: RedirectHop[] = [];
  const currentUrl = targetUrl;

  // 1. Initial SSRF & protocol validation
  const validation = validateSafeUrl(targetUrl, allowLocalIp);
  if (!validation.safe) {
    const endTime = Date.now();
    return {
      url: targetUrl,
      status_code: 400,
      redirects: [],
      headers: {},
      response_time: endTime - startTime,
      html: '',
      error: `SSRF Security Violation: ${validation.reason}`
    };
  }

  // 2. DNS resolution and rebinding validation
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(targetUrl);
  } catch {
    return {
      url: targetUrl,
      status_code: 400,
      redirects: [],
      headers: {},
      response_time: Date.now() - startTime,
      html: '',
      error: 'SSRF Security Violation: Invalid URL format'
    };
  }

  if (!allowLocalIp) {
    const dnsValidation = await resolveAndValidateDns(parsedUrl.hostname, allowLocalIp);
    if (!dnsValidation.safe) {
      const endTime = Date.now();
      return {
        url: targetUrl,
        status_code: 400,
        redirects: [],
        headers: {},
        response_time: endTime - startTime,
        html: '',
        error: `SSRF Security Violation: ${dnsValidation.reason}`
      };
    }
  }

  // Create socket-level safe HTTP/HTTPS agents
  const httpAgent = new http.Agent({
    lookup: createSafeDnsLookup(allowLocalIp),
    keepAlive: false
  });
  const httpsAgent = new https.Agent({
    lookup: createSafeDnsLookup(allowLocalIp),
    keepAlive: false
  });

  try {
    const response = await axios.get(currentUrl, {
      timeout: timeoutMs,
      maxRedirects,
      maxContentLength: maxBytes,
      maxBodyLength: maxBytes,
      httpAgent,
      httpsAgent,
      validateStatus: () => true, // Accept all HTTP status codes without throwing
      headers: {
        'User-Agent': 'SEO-Agent-Bot/1.0 (Compatible; HTTP Fetcher)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
      beforeRedirect: (redirectOptions, responseDetails) => {
        const nextUrl = redirectOptions.href || String(currentUrl);

        // Enforce SSRF check on redirect destination
        const redirectCheck = validateSafeUrl(nextUrl, allowLocalIp);
        if (!redirectCheck.safe) {
          throw new Error(`SSRF Blocked redirect to unsafe URL: ${nextUrl} (${redirectCheck.reason})`);
        }

        redirects.push({
          url: nextUrl,
          status_code: responseDetails.statusCode || 301,
          location: redirectOptions.href
        });
      }
    });

    const endTime = Date.now();
    const responseTime = endTime - startTime;

    // Standardize header keys to lower-case strings
    const rawHeaders = response.headers;
    const headers: Record<string, string> = {};
    for (const [key, val] of Object.entries(rawHeaders)) {
      if (typeof val === 'string') {
        headers[key.toLowerCase()] = val;
      } else if (Array.isArray(val)) {
        headers[key.toLowerCase()] = val.join(', ');
      }
    }

    const finalUrl = response.request?.res?.responseUrl || response.config.url || targetUrl;
    const contentType = headers['content-type'] || 'text/html';
    const html = typeof response.data === 'string' ? response.data : JSON.stringify(response.data);

    return {
      url: finalUrl,
      status_code: response.status,
      redirects,
      headers,
      response_time: responseTime,
      html,
      content_type: contentType
    };
  } catch (err: any) {
    const endTime = Date.now();
    const responseTime = endTime - startTime;
    return {
      url: targetUrl,
      status_code: err.response?.status || (err.message?.includes('SSRF') ? 400 : 500),
      redirects,
      headers: {},
      response_time: responseTime,
      html: '',
      error: err.message || 'Failed to fetch URL'
    };
  }
}
