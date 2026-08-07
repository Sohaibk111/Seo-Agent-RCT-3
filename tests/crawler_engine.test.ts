import { app } from '../server';
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
  console.log('⚙️ Starting Crawler Engine Test Suite...\n');
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
  const orgId = 1;

  // 1. Setup Test Project & Website
  let projRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
    method: 'POST',
    headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'Crawler Engine Suite Proj', slug: 'crawler-engine-suite-proj' })
  });
  let proj = await projRes.json();
  let projectId = proj.id;

  let siteRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${projectId}/websites`, {
    method: 'POST',
    headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain: 'crawler-engine-test.com' })
  });
  let site = await siteRes.json();
  let websiteId = site.id;

  let crawlId = 0;
  let pageId1 = 0;
  let pageId2 = 0;

  // --- TESTS ---

  await test('1. Trigger new crawl job - Initializes status as queued', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${projectId}/websites/${websiteId}/crawls`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ triggered_by: 'manual' })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.ok(data.id);
    assert.strictEqual(data.status, 'queued');
    assert.strictEqual(data.website_id, websiteId);
    crawlId = data.id;
  });

  await test('2. Active crawl conflict guard - Reject second concurrent crawl with 409', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${projectId}/websites/${websiteId}/crawls`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ triggered_by: 'manual' })
    });

    assert.strictEqual(res.status, 409);
    const data = await res.json();
    assert.ok(data.error.includes('already exists for this website'));
  });

  await test('3. Start crawl job - State transitions to running and records started_at', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/start`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, crawlId);
    assert.strictEqual(data.status, 'running');
    assert.ok(data.started_at);
  });

  await test('4. Pause active crawl job - State transitions to paused', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/pause`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.status, 'paused');
  });

  await test('5. Resume paused crawl job - State returns to running', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/resume`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.status, 'running');
  });

  await test('6. Add discovered 200 OK page to crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://crawler-engine-test.com/',
        title: 'Home Page',
        status_code: 200,
        content_type: 'text/html',
        word_count: 450,
        depth: 0
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.ok(data.id);
    assert.strictEqual(data.url, 'https://crawler-engine-test.com/');
    pageId1 = data.id;
  });

  await test('7. Add 404 broken page to crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://crawler-engine-test.com/missing-page',
        title: 'Not Found',
        status_code: 404,
        content_type: 'text/html',
        word_count: 50,
        depth: 1
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.strictEqual(data.status_code, 404);
    pageId2 = data.id;
  });

  await test('8. GET /crawl/:id/status - Real-time statistics calculation', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/status`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.status, 'running');
    assert.strictEqual(data.stats.total_pages, 2);
    assert.strictEqual(data.stats.broken_pages, 1);
  });

  await test('9. GET /crawl/:id/pages - List all pages for crawl job', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/pages`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 2);
    assert.strictEqual(data.pages.length, 2);
  });

  await test('10. GET /crawl/:id/pages?status_code=404 - Filter pages by HTTP status code', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/pages?status_code=404`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 1);
    assert.strictEqual(data.pages[0].status_code, 404);
  });

  await test('11. GET /crawl/:id/pages?search=missing - Search pages by term', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/pages?search=missing`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 1);
    assert.ok(data.pages[0].url.includes('missing-page'));
  });

  await test('12. GET /crawl/:id/pages?skip=0&limit=1 - Paginate crawl pages', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/pages?skip=0&limit=1`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 2);
    assert.strictEqual(data.pages.length, 1);
  });

  await test('13. GET /crawl/:id/page/:page_id - Get page detail', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/page/${pageId1}`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, pageId1);
    assert.strictEqual(data.url, 'https://crawler-engine-test.com/');
  });

  await test('14. Add technical issue to crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/issues`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        page_id: pageId2,
        severity: 'critical',
        category: 'links',
        message: 'Broken link found returning 404 status',
        recommendation: 'Fix or remove dead links'
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.strictEqual(data.message, 'Broken link found returning 404 status');
    assert.strictEqual(data.severity, 'critical');
  });

  await test('15. List technical issues for crawl job with severity filter', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/issues?severity=critical`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 1);
    assert.strictEqual(data.items[0].severity, 'critical');
  });

  await test('16. Stop active crawl job - State transitions to stopped and calculates duration', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/stop`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.status, 'stopped');
    assert.ok(data.finished_at);
  });

  await test('17. Retry stopped/cancelled crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/retry`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.status, 'queued');
  });

  await test('18. Cancel queued crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/cancel`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.status, 'cancelled');
  });

  console.log(`\n🎉 Crawler Engine Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
