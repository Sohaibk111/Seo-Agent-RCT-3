import { app, crawlJobs, crawlPages, websites, projects } from '../server';
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
  console.log('🔄 Starting Crawl Lifecycle & Pages Control Test Suite...\n');
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

  // Setup test environment data
  let projRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
    method: 'POST',
    headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'Lifecycle Test Proj', slug: 'lifecycle-test-proj' })
  });
  let proj = await projRes.json();
  let projectId = proj.id;

  let siteRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${projectId}/websites`, {
    method: 'POST',
    headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain: 'lifecycle-site.com' })
  });
  let site = await siteRes.json();
  let websiteId = site.id;

  let crawlRes = await fetch(`${baseUrl}/api/v1/projects/${projectId}/websites/${websiteId}/crawls`, {
    method: 'POST',
    headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
    body: JSON.stringify({ triggered_by: 'manual' })
  });
  let crawl = await crawlRes.json();
  let crawlId = crawl.id;

  await test('POST /crawl/:id/start - Transitions job to running state and sets started_at', async () => {
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

  await test('POST /crawl/:id/pause - Transitions job to paused state', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/pause`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, crawlId);
    assert.strictEqual(data.status, 'paused');
  });

  await test('POST /crawl/:id/resume - Resumes job back to running state', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/resume`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, crawlId);
    assert.strictEqual(data.status, 'running');
  });

  await test('GET /crawl/:id/status - Retrieves real-time status and crawl metrics', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/status`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, crawlId);
    assert.strictEqual(data.status, 'running');
    assert.ok(data.stats);
  });

  // Add pages to crawl job for pages list and detail testing
  let p1Res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/pages`, {
    method: 'POST',
    headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: 'https://lifecycle-site.com/',
      title: 'Homepage',
      status_code: 200,
      word_count: 520
    })
  });
  let page1 = await p1Res.json();

  let p2Res = await fetch(`${baseUrl}/api/v1/crawls/${crawlId}/pages`, {
    method: 'POST',
    headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: 'https://lifecycle-site.com/about',
      title: 'About Us',
      status_code: 200,
      word_count: 310
    })
  });
  let page2 = await p2Res.json();

  await test('GET /crawl/:id/pages - List all discovered pages for crawl job', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/pages`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.crawl_id, crawlId);
    assert.strictEqual(data.total, 2);
    assert.ok(Array.isArray(data.pages));
    assert.strictEqual(data.pages.length, 2);
  });

  await test('GET /crawl/:id/page/:page_id - Get specific page details', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/page/${page1.id}`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, page1.id);
    assert.strictEqual(data.url, 'https://lifecycle-site.com/');
    assert.strictEqual(data.title, 'Homepage');
  });

  await test('GET /crawl/:id/page/:page_id - Non-existent page returns 404', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/page/999999`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 404);
  });

  await test('POST /crawl/:id/stop - Stops crawl job and sets finished_at', async () => {
    const res = await fetch(`${baseUrl}/crawl/${crawlId}/stop`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, crawlId);
    assert.strictEqual(data.status, 'stopped');
    assert.ok(data.finished_at);
  });

  console.log(`\n🎉 Crawl Lifecycle Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
