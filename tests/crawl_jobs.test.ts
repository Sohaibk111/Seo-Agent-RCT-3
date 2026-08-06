import { app, crawlJobs, crawlPages, crawlIssues, websites, projects, orgMembers } from '../server';
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
  console.log('📂 Starting Website Crawl & Technical SEO Infrastructure Test Suite...\n');
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

  const tokenUserA = 'Bearer token_user_1';
  const tokenUserB = 'Bearer token_user_2';
  const orgId = 1;

  // Setup initial test data if missing
  let project1Id = 1;
  let existingProj = projects.find(p => p.organization_id === orgId && p.slug === 'crawl-test-proj');
  if (!existingProj) {
    const projRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Crawl Test Proj', slug: 'crawl-test-proj' })
    });
    const projData = await projRes.json();
    project1Id = projData.id;
  } else {
    project1Id = existingProj.id;
  }

  let website1Id = 1;
  let existingWeb = websites.find(w => w.project_id === project1Id && w.domain === 'crawltest.com');
  if (!existingWeb) {
    const webRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: 'crawltest.com', protocol: 'https' })
    });
    const webData = await webRes.json();
    website1Id = webData.id;
  } else {
    website1Id = existingWeb.id;
  }

  let testCrawlId = 0;

  // --- 1. AUTHENTICATION & SECURITY TESTS ---
  await test('POST /crawls - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${project1Id}/websites/${website1Id}/crawls`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ triggered_by: 'manual' })
    });
    assert.strictEqual(res.status, 401);
  });

  await test('GET /crawls - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${project1Id}/websites/${website1Id}/crawls`);
    assert.strictEqual(res.status, 401);
  });

  await test('GET /crawls/:id - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/999`);
    assert.strictEqual(res.status, 401);
  });

  await test('POST /crawls/:id/cancel - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/999/cancel`, { method: 'POST' });
    assert.strictEqual(res.status, 401);
  });

  await test('POST /crawls/:id/retry - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/999/retry`, { method: 'POST' });
    assert.strictEqual(res.status, 401);
  });

  await test('GET /crawls/:id/pages - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/999/pages`);
    assert.strictEqual(res.status, 401);
  });

  await test('GET /crawls/:id/issues - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/999/issues`);
    assert.strictEqual(res.status, 401);
  });

  await test('PATCH /crawls/:id/progress - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/999/progress`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ progress: 50 })
    });
    assert.strictEqual(res.status, 401);
  });

  // --- 2. RESOURCE NOT FOUND & VALIDATION TESTS ---
  await test('POST /crawls - Non-existent project returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/999999/websites/${website1Id}/crawls`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ triggered_by: 'manual' })
    });
    assert.strictEqual(res.status, 404);
  });

  await test('POST /crawls - Non-existent website in project returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${project1Id}/websites/999999/crawls`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ triggered_by: 'manual' })
    });
    assert.strictEqual(res.status, 404);
  });

  await test('GET /crawls/:id - Non-existent crawl job returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/999999`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 404);
  });

  // --- 3. CRAWL CREATION & ACTIVE CONFLICT GUARD ---
  await test('POST /crawls - Successfully trigger new crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${project1Id}/websites/${website1Id}/crawls`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ triggered_by: 'manual', crawler_version: '1.2.0' })
    });
    assert.strictEqual(res.status, 201);
    const body = await res.json();
    assert.ok(body.id > 0);
    assert.strictEqual(body.website_id, website1Id);
    assert.strictEqual(body.status, 'queued');
    assert.strictEqual(body.progress, 0);
    assert.strictEqual(body.pages_found, 0);
    assert.strictEqual(body.issues_found, 0);
    assert.strictEqual(body.triggered_by, 'manual');
    assert.strictEqual(body.crawler_version, '1.2.0');
    assert.ok(body.stats);
    assert.strictEqual(body.stats.total_pages, 0);
    testCrawlId = body.id;
  });

  await test('POST /crawls - Active crawl conflict guard returns 409 Conflict', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${project1Id}/websites/${website1Id}/crawls`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ triggered_by: 'manual' })
    });
    assert.strictEqual(res.status, 409);
    const body = await res.json();
    assert.ok(body.error.includes('active crawl job'));
  });

  // --- 4. CRAWL DETAILS & LISTING ---
  await test('GET /crawls/:id - Retrieve crawl job details with stats', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.id, testCrawlId);
    assert.strictEqual(body.status, 'queued');
    assert.ok(body.stats);
  });

  await test('GET /crawls - List crawl jobs for website with pagination', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/${project1Id}/websites/${website1Id}/crawls?skip=0&limit=10`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.ok(Array.isArray(body.items));
    assert.ok(body.total >= 1);
    assert.strictEqual(body.items[0].id, testCrawlId);
  });

  // --- 5. PROGRESS UPDATE & STATUS TRANSITIONS ---
  await test('PATCH /crawls/:id/progress - Transition queued to running', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/progress`, {
      method: 'PATCH',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'running', progress: 10 })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.status, 'running');
    assert.strictEqual(body.progress, 10);
    assert.ok(body.started_at);
  });

  await test('PATCH /crawls/:id/progress - Update progress percentage and metrics', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/progress`, {
      method: 'PATCH',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ progress: 50, pages_found: 5, issues_found: 2 })
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.progress, 50);
    assert.strictEqual(body.pages_found, 5);
    assert.strictEqual(body.issues_found, 2);
  });

  // --- 6. CRAWL PAGES ENGINE HOOK & QUERYING ---
  let page1Id = 0;
  await test('POST /crawls/:id/pages - Add discovered page', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://crawltest.com/',
        depth: 0,
        status_code: 200,
        content_type: 'text/html; charset=utf-8',
        title: 'Crawl Test Homepage',
        meta_description: 'Welcome to crawl test homepage.',
        h1: 'Main Heading',
        word_count: 450,
        internal_links: 12,
        external_links: 3,
        response_time: 180
      })
    });
    assert.strictEqual(res.status, 201);
    const body = await res.json();
    assert.ok(body.id > 0);
    assert.strictEqual(body.url, 'https://crawltest.com/');
    assert.strictEqual(body.title, 'Crawl Test Homepage');
    page1Id = body.id;
  });

  await test('POST /crawls/:id/pages - Add a 404 broken page', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://crawltest.com/broken-link',
        depth: 1,
        status_code: 404,
        content_type: 'text/html',
        title: '404 Not Found',
        word_count: 50,
        response_time: 220
      })
    });
    assert.strictEqual(res.status, 201);
  });

  await test('GET /crawls/:id/pages - List all crawl pages', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/pages`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.total, 2);
    assert.strictEqual(body.items.length, 2);
  });

  await test('GET /crawls/:id/pages - Filter pages by status_code', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/pages?status_code=404`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.total, 1);
    assert.strictEqual(body.items[0].status_code, 404);
  });

  await test('GET /crawls/:id/pages - Search pages by URL term', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/pages?search=broken`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.total, 1);
    assert.strictEqual(body.items[0].url, 'https://crawltest.com/broken-link');
  });

  // --- 7. CRAWL ISSUES ENGINE HOOK & QUERYING ---
  await test('POST /crawls/:id/issues - Add technical SEO issue', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/issues`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        page_id: page1Id,
        severity: 'high',
        category: 'missing_meta_description',
        message: 'Meta description is too short or missing',
        recommendation: 'Provide a compelling meta description between 120 and 160 characters.'
      })
    });
    assert.strictEqual(res.status, 201);
    const body = await res.json();
    assert.ok(body.id > 0);
    assert.strictEqual(body.severity, 'high');
    assert.strictEqual(body.category, 'missing_meta_description');
  });

  await test('POST /crawls/:id/issues - Add critical broken link issue', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/issues`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        severity: 'critical',
        category: 'broken_internal_link',
        message: 'Internal link returned 404 HTTP status code',
        recommendation: 'Fix or remove dead links.'
      })
    });
    assert.strictEqual(res.status, 201);
  });

  await test('GET /crawls/:id/issues - List all crawl issues', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/issues`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.total, 2);
  });

  await test('GET /crawls/:id/issues - Filter issues by severity', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/issues?severity=critical`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.total, 1);
    assert.strictEqual(body.items[0].severity, 'critical');
  });

  await test('GET /crawls/:id/issues - Filter issues by category', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/issues?category=missing_meta_description`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.total, 1);
    assert.strictEqual(body.items[0].category, 'missing_meta_description');
  });

  // --- 8. STATS COMPUTATION VERIFICATION ---
  await test('GET /crawls/:id - Verify updated stats calculation', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.ok(body.stats);
    assert.strictEqual(body.stats.total_pages, 2);
    assert.strictEqual(body.stats.html_pages, 2);
    assert.strictEqual(body.stats.broken_pages, 1);
    assert.strictEqual(body.stats.average_response_time, 200); // (180 + 220) / 2 = 200
  });

  // --- 9. CANCEL & RETRY STATE MACHINE OPERATIONS ---
  await test('POST /crawls/:id/cancel - Cancel active crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/cancel`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.status, 'cancelled');
    assert.ok(body.finished_at);
  });

  await test('POST /crawls/:id/cancel - Attempting to cancel already cancelled job returns 409', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/cancel`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 409);
  });

  await test('POST /crawls/:id/retry - Retry cancelled crawl job', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/retry`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.status, 'queued');
    assert.strictEqual(body.progress, 0);
    assert.strictEqual(body.started_at, null);
    assert.strictEqual(body.finished_at, null);
  });

  await test('POST /crawls/:id/retry - Attempting to retry queued job returns 409', async () => {
    const res = await fetch(`${baseUrl}/api/v1/crawls/${testCrawlId}/retry`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 409);
  });

  // Cleanup server
  await stopTestServer();

  console.log(`\n🎉 Test Suite Completed: ${passedCount} passed, ${failedCount} failed.\n`);
  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests().catch((err) => {
  console.error('Test runner fatal error:', err);
  process.exit(1);
});
