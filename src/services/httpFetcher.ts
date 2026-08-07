import axios from 'axios';

export interface RedirectHop {
  url: string;
  status_code: number;
  location?: string;
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
 * Fetches an HTTP URL and collects status code, redirects, response headers, response time, and HTML content.
 */
export async function fetchUrl(targetUrl: string, timeoutMs: number = 10000): Promise<FetchResult> {
  const startTime = Date.now();
  const redirects: RedirectHop[] = [];
  const currentUrl = targetUrl;

  try {
    const response = await axios.get(currentUrl, {
      timeout: timeoutMs,
      maxRedirects: 5,
      validateStatus: () => true, // Accept all HTTP status codes without throwing
      headers: {
        'User-Agent': 'SEO-Agent-Bot/1.0 (Compatible; HTTP Fetcher)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
      beforeRedirect: (options, responseDetails) => {
        redirects.push({
          url: options.href || String(currentUrl),
          status_code: responseDetails.statusCode || 301,
          location: options.href
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
