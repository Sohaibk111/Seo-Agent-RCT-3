import { app } from '../server';
import { fetchUrl } from '../src/services/httpFetcher';
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

  // --- 1. DIRECT SERVICE TESTS FOR HTTP FETCHING ---
  await test('fetchUrl - Collect status code, response headers, response time, and HTML', async () => {
    const targetUrl = `${baseUrl}/test-target/page1`;
    const res = await fetchUrl(targetUrl);

    assert.strictEqual(res.status_code, 200);
    assert.strictEqual(typeof res.response_time, 'number');
    assert.strictEqual(res.response_time >= 0, true);
    assert.strictEqual(res.headers['x-custom-header'], 'SEO-Agent-Test');
    assert.strictEqual(res.headers['content-type']?.includes('text/html'), true);
    assert.strictEqual(res.html.includes('<h1>Hello HTTP Fetcher</h1>'), true);
  });

  await test('fetchUrl - Collect redirects chain', async () => {
    const targetUrl = `${baseUrl}/test-target/redirect-source`;
    const res = await fetchUrl(targetUrl);

    assert.strictEqual(res.status_code, 200);
    assert.strictEqual(res.redirects.length > 0, true);
    assert.strictEqual(res.redirects[0].status_code, 301);
    assert.strictEqual(res.html.includes('<h1>Hello HTTP Fetcher</h1>'), true);
  });

  await test('fetchUrl - Collect 404 status code and HTML', async () => {
    const targetUrl = `${baseUrl}/test-target/404`;
    const res = await fetchUrl(targetUrl);

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
      body: JSON.stringify({ url: `${baseUrl}/test-target/page1` })
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

  console.log(`\n🎉 HTTP Fetching Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
