import { app, websites, projects } from '../server';
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
  console.log('📂 Starting Website Management Test Suite...\n');
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

  // First ensure test project exists in org 1
  let project1Id = 1;
  const existingProj = projects.find(p => p.organization_id === orgId && p.slug === 'web-test-proj');
  if (!existingProj) {
    const projRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Web Test Proj', slug: 'web-test-proj' })
    });
    if (projRes.status === 201) {
      const pData = await projRes.json();
      project1Id = pData.id;
    }
  } else {
    project1Id = existingProj.id;
  }

  // 1. Unauthenticated Security Tests (401)
  await test('Unauthenticated POST website returns 401', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: 'unauth.com' })
    });
    assert.strictEqual(res.status, 401);
  });

  await test('Unauthenticated GET websites returns 401', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites`);
    assert.strictEqual(res.status, 401);
  });

  // 2. Domain Validation & Normalization
  await test('Invalid domain format returns 422', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: 'invalid_domain_name_without_tld' })
    });
    assert.strictEqual(res.status, 422);
  });

  let createdWebsiteId: number;
  await test('Create Website with domain normalization', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'https://WWW.Alpha-Brand.COM/path?query=1',
        protocol: 'https',
        status: 'active',
        country: 'US',
        language: 'en',
        settings: { crawl_frequency: 'daily' }
      })
    });
    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.ok(data.id);
    assert.strictEqual(data.normalized_domain, 'alpha-brand.com');
    assert.strictEqual(data.organization_id, orgId);
    assert.strictEqual(data.project_id, project1Id);
    assert.strictEqual(data.url, 'https://alpha-brand.com');
    assert.strictEqual(data.settings.crawl_frequency, 'daily');
    createdWebsiteId = data.id;
  });

  // 3. Duplicate Prevention within Organization
  await test('Duplicate domain in same org returns 409', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'ALPHA-BRAND.COM'
      })
    });
    assert.strictEqual(res.status, 409);
  });

  // 4. Get Website By ID and By Domain
  await test('Get Website by ID', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, createdWebsiteId);
    assert.strictEqual(data.normalized_domain, 'alpha-brand.com');
  });

  await test('Get Website by Domain Name', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/alpha-brand.com`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, createdWebsiteId);
  });

  // 5. Update Website & Settings
  await test('Update Website settings and attributes', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}`, {
      method: 'PUT',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        country: 'CA',
        settings: { crawl_frequency: 'weekly', max_pages: 500 }
      })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.country, 'CA');
    assert.strictEqual(data.settings.max_pages, 500);
  });

  await test('PUT /settings endpoint updates settings', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}/settings`, {
      method: 'PUT',
      headers: { 'Authorization': tokenUserA, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        settings: { crawl_frequency: 'monthly', notify_email: 'alerts@alpha-brand.com' }
      })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.settings.notify_email, 'alerts@alpha-brand.com');
  });

  await test('GET /settings returns settings dictionary', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}/settings`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.website_id, createdWebsiteId);
    assert.strictEqual(data.settings.notify_email, 'alerts@alpha-brand.com');
  });

  // 6. Metadata and Stats Endpoints
  await test('GET /metadata returns website structural details', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}/metadata`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.website_id, createdWebsiteId);
    assert.strictEqual(data.domain, 'alpha-brand.com');
    assert.strictEqual(typeof data.settings_count, 'number');
  });

  await test('GET /stats returns metrics and counts', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}/stats`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.website_id, createdWebsiteId);
    assert.strictEqual(typeof data.total_audits, 'number');
    assert.strictEqual(typeof data.created_days_ago, 'number');
  });

  // 7. Archive and Restore
  await test('Archive website', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}/archive`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.archived, true);
    assert.strictEqual(data.status, 'archived');
  });

  await test('List websites filtered by archived state', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites?archived=true`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.ok(data.some((w: any) => w.id === createdWebsiteId));
  });

  await test('Restore website', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}/restore`, {
      method: 'POST',
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.archived, false);
    assert.strictEqual(data.status, 'active');
  });

  // 8. Project & Org Isolation
  await test('Requesting website under invalid project returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/99999/websites/${createdWebsiteId}`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 404);
  });

  // 9. Delete Website
  await test('Delete website', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}`, {
      method: 'DELETE',
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, createdWebsiteId);

    // Verify deleted
    const checkRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${project1Id}/websites/${createdWebsiteId}`, {
      headers: { 'Authorization': tokenUserA }
    });
    assert.strictEqual(checkRes.status, 404);
  });

  await stopTestServer();

  console.log(`\n🏁 Test Suite Complete: ${passedCount} Passed, ${failedCount} Failed.`);
  if (failedCount > 0) {
    process.exit(1);
  }
  process.exit(0);
}

runTests();
