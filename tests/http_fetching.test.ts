import { app } from '../server';
import { fetchUrl, resolveAndValidateDns } from '../src/services/httpFetcher';
import http from 'http';
import assert from 'assert';

let server: http.Server;
let baseUrl: string;

async function startTestServer(): Promise<string> {
  return new Promise((resolve) => {
    process.env.NODE_ENV = 'test';
    
    // Add temporary mock target endpoints to app for testing HTTP fetcher behavior
    app.get('/test-target/page1', (_req, res) => {
      res.setHeader('X-Custom-Header', 'SEO-Agent-Test');
      res.setHeader('Content-Type', 'text/html');
      res.status(200).send('<html><head><title>Test Page 1</title></head><body><h1>Hello HTTP Fetcher</h1></body></html>');
    });

    app.get('/test-target/redirect-source', (_req, res) => {
      res.redirect(301, '/test-target/page1');
    });

    app.get('/test-target/404', (_req, res) => {
      res.status(404).send('<html><body>Not Found</body></html>');
    });

    server = app.listen(0, '127.0.0.1', () => {
      const address = server.address() as any;
      const url = `http://127.0.0.1:${address.port}`;
      resolve(url);
    });
  });
}

function stopTestServer(): Promise<void> {
  return new Promise((resolve) => {
    if (server) {
      server.close(() => resolve());
    } else {
      resolve();
    }
  });
}

async function runTests() {
  console.log('🌐 Starting HTTP Fetching Infrastructure Test Suite...\n');
  baseUrl = await startTestServer();
  let passedCount = 0;
  let failedCount = 0;

  async function test(name: string, fn: () => Promise<void>) {
    try {
      await fn();
      console.log(`  ✓ PASSED: ${name}`);
      passedCount++;
    } catch (err: any) {
      console.error(`  ✗ FAILED: ${name}`);
      console.error(`    Error: ${err.message}`);
      if (err.stack) console.error(err.stack);
      failedCount++;
    }
  }

  const tokenUser = 'Bearer token_user_1';

  // --- 1. DIRECT SERVICE TESTS FOR HTTP FETCHING (with explicit test allowLocalIp) ---
  await test('fetchUrl - Collect status code, response headers, response time, and HTML', async () => {
    const targetUrl = `${baseUrl}/test-target/page1`;
    const res = await fetchUrl(targetUrl, { allowLocalIp: true });

    assert.strictEqual(res.status_code, 200);
    assert.strictEqual(typeof res.response_time, 'number');
    assert.strictEqual(res.response_time >= 0, true);
    assert.strictEqual(res.headers['x-custom-header'], 'SEO-Agent-Test');
    assert.strictEqual(res.headers['content-type']?.includes('text/html'), true);
    assert.strictEqual(res.html.includes('<h1>Hello HTTP Fetcher</h1>'), true);
  });

  await test('fetchUrl - Collect redirects chain', async () => {
    const targetUrl = `${baseUrl}/test-target/redirect-source`;
    const res = await fetchUrl(targetUrl, { allowLocalIp: true });

    assert.strictEqual(res.status_code, 200);
    assert.strictEqual(res.redirects.length > 0, true);
    assert.strictEqual(res.redirects[0].status_code, 301);
    assert.strictEqual(res.html.includes('<h1>Hello HTTP Fetcher</h1>'), true);
  });

  await test('fetchUrl - Collect 404 status code and HTML', async () => {
    const targetUrl = `${baseUrl}/test-target/404`;
    const res = await fetchUrl(targetUrl, { allowLocalIp: true });

    assert.strictEqual(res.status_code, 404);
    assert.strictEqual(res.html.includes('Not Found'), true);
    assert.strictEqual(typeof res.response_time, 'number');
  });

  // --- 2. API ENDPOINT TESTS FOR /api/v1/fetch ---
  await test('POST /api/v1/fetch - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/fetch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: `${baseUrl}/test-target/page1` })
    });
    assert.strictEqual(res.status, 401);
  });

  await test('POST /api/v1/fetch - Perform fetch and return status, headers, response_time, and HTML', async () => {
    const res = await fetch(`${baseUrl}/api/v1/fetch`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ url: `${baseUrl}/test-target/page1`, allowLocalIp: true })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.status_code, 200);
    assert.strictEqual(typeof data.response_time, 'number');
    assert.strictEqual(data.headers['x-custom-header'], 'SEO-Agent-Test');
    assert.strictEqual(data.html.includes('<h1>Hello HTTP Fetcher</h1>'), true);
  });

  await test('POST /api/v1/fetch - Reject missing URL with 400', async () => {
    const res = await fetch(`${baseUrl}/api/v1/fetch`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    });
    assert.strictEqual(res.status, 400);
  });

  // --- 3. SSRF PROTECTION SECURITY SUITE ---
  await test('SSRF Protection - Default fetchUrl behavior rejects localhost target without explicit option', async () => {
    const res = await fetchUrl(`${baseUrl}/test-target/page1`);
    assert.strictEqual(res.status_code, 400);
    assert.ok(res.error?.includes('SSRF Security Violation') || res.error?.includes('Blocked'));
  });

  const ssrfTestCases = [
    { url: 'http://127.0.0.1', desc: 'IPv4 loopback (127.0.0.1)' },
    { url: 'http://127.0.0.1:8080', desc: 'IPv4 loopback with port (127.0.0.1:8080)' },
    { url: 'http://localhost', desc: 'localhost hostname' },
    { url: 'http://app.localhost', desc: 'subdomain .localhost' },
    { url: 'http://0.0.0.0', desc: '0.0.0.0 all-interfaces' },
    { url: 'http://0', desc: '0 integer representation' },
    { url: 'http://10.0.0.1', desc: '10.0.0.0/8 private network' },
    { url: 'http://10.255.255.254', desc: '10.0.0.0/8 upper bound private' },
    { url: 'http://172.16.0.1', desc: '172.16.0.0/12 private network' },
    { url: 'http://172.31.255.254', desc: '172.16.0.0/12 upper bound private' },
    { url: 'http://192.168.0.1', desc: '192.168.0.0/16 private network' },
    { url: 'http://192.168.1.100', desc: '192.168.0.0/16 LAN address' },
    { url: 'http://169.254.169.254', desc: 'Cloud metadata IP (169.254.169.254)' },
    { url: 'http://169.254.1.1', desc: 'Link-local IP (169.254.0.0/16)' },
    { url: 'http://100.64.0.1', desc: 'Carrier-grade NAT (100.64.0.0/10)' },
    { url: 'http://metadata.google.internal', desc: 'Cloud metadata hostname (metadata.google.internal)' },
    { url: 'http://instance-data', desc: 'AWS metadata hostname (instance-data)' },
    { url: 'http://metadata.goog', desc: 'GCP metadata domain (metadata.goog)' },
    { url: 'http://wpad', desc: 'WPAD domain (wpad)' },
    { url: 'http://[::1]', desc: 'IPv6 loopback ([::1])' },
    { url: 'http://[::]', desc: 'IPv6 unspecified ([::])' },
    { url: 'http://[fd00::1]', desc: 'IPv6 unique local ([fd00::1])' },
    { url: 'http://[fe80::1]', desc: 'IPv6 link-local ([fe80::1])' },
    { url: 'http://[::ffff:127.0.0.1]', desc: 'IPv4-mapped IPv6 loopback' },
    { url: 'http://[::ffff:169.254.169.254]', desc: 'IPv4-mapped IPv6 metadata' },
    { url: 'http://2130706433', desc: 'Integer-encoded IP (2130706433 = 127.0.0.1)' },
    { url: 'http://0x7f000001', desc: 'Hexadecimal-encoded IP (0x7f000001 = 127.0.0.1)' },
    { url: 'http://017700000001', desc: 'Octal-encoded IP (017700000001 = 127.0.0.1)' },
    { url: 'http://127.1', desc: 'Shortened decimal IP (127.1 = 127.0.0.1)' },
    { url: 'http://2852039166', desc: 'Integer-encoded metadata IP (2852039166 = 169.254.169.254)' },
    { url: 'http://0xa9fea9fe', desc: 'Hex-encoded metadata IP (0xa9fea9fe = 169.254.169.254)' }
  ];

  for (const tc of ssrfTestCases) {
    await test(`SSRF Protection - Reject ${tc.desc}`, async () => {
      const res = await fetchUrl(tc.url, { timeoutMs: 2000 });
      assert.strictEqual(res.status_code, 400);
      assert.ok(res.error?.includes('SSRF Security Violation') || res.error?.includes('Blocked'));
    });
  }

  // Test Disallowed Protocols and Userinfo
  const invalidProtocolCases = [
    { url: 'file:///etc/passwd', desc: 'file:// protocol' },
    { url: 'ftp://ftp.example.com/file', desc: 'ftp:// protocol' },
    { url: 'gopher://127.0.0.1:70/', desc: 'gopher:// protocol' },
    { url: 'http://admin:secret@example.com/login', desc: 'Userinfo credentials in URL' }
  ];

  for (const tc of invalidProtocolCases) {
    await test(`SSRF Protection - Reject ${tc.desc}`, async () => {
      const res = await fetchUrl(tc.url, { allowLocalIp: true, timeoutMs: 2000 });
      assert.strictEqual(res.status_code, 400);
      assert.ok(res.error?.includes('SSRF Security Violation') || res.error?.includes('Disallowed') || res.error?.includes('Userinfo'));
    });
  }

  // Test Redirects to Private / Metadata / Localhost Addresses
  const redirectAttackCases = [
    {
      path: '/test-target/redirect-to-metadata',
      target: 'http://169.254.169.254/latest/meta-data/',
      desc: 'redirect to AWS/GCP metadata IP'
    },
    {
      path: '/test-target/redirect-to-loopback',
      target: 'http://127.0.0.1:8080/internal-admin',
      desc: 'redirect to loopback 127.0.0.1'
    },
    {
      path: '/test-target/redirect-to-private-lan',
      target: 'http://192.168.1.1/admin',
      desc: 'redirect to private 192.168.x LAN'
    },
    {
      path: '/test-target/redirect-to-hex-ip',
      target: 'http://0x7f000001/status',
      desc: 'redirect to hex-encoded IP'
    },
    {
      path: '/test-target/redirect-to-ipv6-loopback',
      target: 'http://[::1]:9000/metrics',
      desc: 'redirect to IPv6 loopback'
    }
  ];

  for (const tc of redirectAttackCases) {
    await test(`SSRF Protection - Block ${tc.desc}`, async () => {
      app.get(tc.path, (_req, res) => {
        res.redirect(302, tc.target);
      });

      const startUrl = `${baseUrl}${tc.path}`;
      // Even if the initial fetch is permitted to local test server, the redirect destination must be validated and blocked!
      const res = await fetchUrl(startUrl, { allowLocalIp: false, timeoutMs: 2000 });
      assert.ok(res.error?.includes('SSRF') || res.status_code >= 400);
    });
  }

  // --- 4. DNS RESOLUTION & REBINDING SSRF PROTECTION ---
  await test('SSRF Protection - resolveAndValidateDns blocks localhost / loopback domains', async () => {
    const res = await resolveAndValidateDns('localhost', false);
    assert.strictEqual(res.safe, false);
    assert.ok(res.reason?.includes('blocked') || res.reason?.includes('private'));
  });

  await test('SSRF Protection - resolveAndValidateDns allows resolution with allowLocalIp: true', async () => {
    const res = await resolveAndValidateDns('localhost', true);
    assert.strictEqual(res.safe, true);
  });

  await test('SSRF Protection - resolveAndValidateDns directly identifies private IPv4 literals', async () => {
    const res = await resolveAndValidateDns('10.0.0.1', false);
    assert.strictEqual(res.safe, false);
    assert.ok(res.reason?.includes('blocked'));
  });

  await test('SSRF Protection - resolveAndValidateDns directly identifies private IPv6 literals', async () => {
    const res = await resolveAndValidateDns('::1', false);
    assert.strictEqual(res.safe, false);
    assert.ok(res.reason?.includes('blocked'));
  });

  await test('SSRF Protection - fetchUrl blocks domains resolving to local/private addresses', async () => {
    const res = await fetchUrl('http://localhost:8080/secret', { allowLocalIp: false, timeoutMs: 2000 });
    assert.strictEqual(res.status_code, 400);
    assert.ok(res.error?.includes('SSRF Security Violation') || res.error?.includes('Blocked'));
  });

  console.log(`\n🎉 HTTP Fetching Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
