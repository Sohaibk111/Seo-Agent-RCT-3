import { app } from '../server';
import { RobotsParser, parseRobotsTxt } from '../src/services/robotsParser';
import http from 'http';
import assert from 'assert';

let server: http.Server;
let baseUrl: string;

async function startTestServer(): Promise<string> {
  return new Promise((resolve) => {
    process.env.NODE_ENV = 'test';
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
  console.log('🤖 Starting Robots.txt Parsing Test Suite...\n');
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

  const sampleRobotsTxt = `
# Robots.txt for example.com
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /private/public-page
Crawl-delay: 5

User-agent: Googlebot
Disallow: /no-google/
Crawl-delay: 2

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-news.xml
  `;

  const tokenUser = 'Bearer token_user_1';

  // --- 1. DIRECT SERVICE TESTS FOR ROBOTS PARSER ---
  await test('RobotsParser - Extract sitemaps', async () => {
    const parser = new RobotsParser(sampleRobotsTxt);
    assert.strictEqual(parser.sitemaps.length, 2);
    assert.strictEqual(parser.sitemaps[0], 'https://example.com/sitemap.xml');
    assert.strictEqual(parser.sitemaps[1], 'https://example.com/sitemap-news.xml');
  });

  await test('RobotsParser - Extract Crawl-delay', async () => {
    const parser = new RobotsParser(sampleRobotsTxt);
    assert.strictEqual(parser.getCrawlDelay('*'), 5);
    assert.strictEqual(parser.getCrawlDelay('googlebot'), 2);
  });

  await test('RobotsParser - Allow / Disallow path checking with prefix specificity', async () => {
    const parser = new RobotsParser(sampleRobotsTxt);

    // Disallowed path
    assert.strictEqual(parser.isAllowed('/admin/dashboard', '*'), false);

    // Explicitly allowed path overriding broader disallow
    assert.strictEqual(parser.isAllowed('/private/public-page', '*'), true);

    // Disallowed path under broader disallow
    assert.strictEqual(parser.isAllowed('/private/secret', '*'), false);

    // Allowed path
    assert.strictEqual(parser.isAllowed('/blog/post-1', '*'), true);

    // Googlebot specific disallow
    assert.strictEqual(parser.isAllowed('/no-google/page', 'Googlebot'), false);
    assert.strictEqual(parser.isAllowed('/no-google/page', '*'), true);
  });

  // --- 2. API ENDPOINT TESTS FOR /api/v1/parse-robots ---
  await test('POST /api/v1/parse-robots - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-robots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: sampleRobotsTxt })
    });
    assert.strictEqual(res.status, 401);
  });

  await test('POST /api/v1/parse-robots - Parse robots.txt and verify response', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-robots`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content: sampleRobotsTxt,
        userAgent: '*',
        path: '/admin/settings'
      })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();

    assert.strictEqual(data.sitemaps.length, 2);
    assert.strictEqual(data.crawlDelay, 5);
    assert.strictEqual(data.isAllowed, false);
    assert.ok(data.disallow.includes('/admin/'));
  });

  await test('POST /api/v1/parse-robots - Reject missing content string with 400', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-robots`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    });
    assert.strictEqual(res.status, 400);
  });

  console.log(`\n🎉 Robots.txt Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
