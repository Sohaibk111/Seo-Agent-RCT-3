import axios from 'axios';

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

  const [b0, b1] = parts;

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

  // 224.0.0.0/4 (Multicast: 224.0.0.0 - 239.255.255.255)
  if (b0 >= 224 && b0 <= 239) return true;

  // 240.0.0.0/4 (Reserved / Future use & Broadcast 255.255.255.255)
  if (b0 >= 240) return true;

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
    'metadata'
  ];
  if (cloudMetadataHosts.includes(hostname)) {
    return { safe: false, reason: `Blocked access to cloud metadata host: ${hostname}` };
  }

  // If local IPs are explicitly allowed (e.g. inside local testing environment)
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
    hostname === '[::1]'
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
  const cleanIpv6 = hostname.replace(/^\[|\]$/g, '');
  if (cleanIpv6.includes(':')) {
    if (
      cleanIpv6 === '::1' ||
      cleanIpv6 === '::' ||
      cleanIpv6.startsWith('fc') ||
      cleanIpv6.startsWith('fd') ||
      cleanIpv6.startsWith('fe80') ||
      cleanIpv6.startsWith('::ffff:127.') ||
      cleanIpv6.startsWith('::ffff:10.') ||
      cleanIpv6.startsWith('::ffff:192.168.') ||
      cleanIpv6.startsWith('::ffff:172.')
    ) {
      return { safe: false, reason: `Blocked private/loopback IPv6 address: ${hostname}` };
    }
  }

  return { safe: true };
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
  const allowLocalIp = options.allowLocalIp ?? (process.env.NODE_ENV === 'test');
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

  try {
    const response = await axios.get(currentUrl, {
      timeout: timeoutMs,
      maxRedirects,
      maxContentLength: maxBytes,
      maxBodyLength: maxBytes,
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
      status_code: err.response?.status || 500,
      redirects,
      headers: {},
      response_time: responseTime,
      html: '',
      error: err.message || 'Failed to fetch URL'
    };
  }
}
