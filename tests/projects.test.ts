import { app, projects } from '../server';
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
  console.log('📂 Starting Project Management Foundation Test Suite...\n');
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
      failedCount++;
    }
  }

  const tokenUserA = 'Bearer token_user_1';
  const tokenUserB = 'Bearer token_user_2';
  const orgId = 1;

  // 1. Unauthenticated Security Tests (401)
  await test('Unauthenticated POST /api/v1/orgs/1/projects returns 401', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Unauth Project' })
    });
    assert.strictEqual(res.status, 401);
  });

  await test('Unauthenticated GET /api/v1/orgs/1/projects returns 401', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects`);
    assert.strictEqual(res.status, 401);
  });

  // 2. Project Creation & Auto-Slug Generation
  let createdProjectId: number;
  let createdProjectSlug: string;

  await test('Create project with explicit name and settings', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: tokenUserA
      },
      body: JSON.stringify({
        name: 'E-Commerce SEO Campaign',
        slug: 'ecommerce-seo',
        description: 'Primary organic growth initiative for e-commerce division',
        status: 'active',
        color: '#3B82F6',
        icon: 'folder-shopping',
        timezone: 'America/New_York',
        language: 'en',
        settings: { crawl_frequency: 'daily', target_pages: 500 }
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.strictEqual(data.name, 'E-Commerce SEO Campaign');
    assert.strictEqual(data.slug, 'ecommerce-seo');
    assert.strictEqual(data.organization_id, orgId);
    assert.strictEqual(data.archived, false);
    assert.strictEqual(data.settings.crawl_frequency, 'daily');
    createdProjectId = data.id;
    createdProjectSlug = data.slug;
  });

  await test('Create project with auto-generated slug from name', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: tokenUserA
      },
      body: JSON.stringify({
        name: 'SaaS Product Launch 2026!'
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.strictEqual(data.name, 'SaaS Product Launch 2026!');
    assert.strictEqual(data.slug, 'saas-product-launch-2026');
  });

  // 3. Uniqueness Enforcement (409 Conflict)
  await test('Creating duplicate slug in same org returns 409 Conflict', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: tokenUserA
      },
      body: JSON.stringify({
        name: 'Duplicate E-Commerce Campaign',
        slug: 'ecommerce-seo'
      })
    });

    assert.strictEqual(res.status, 409);
  });

  // 4. Validation Enforcement (422 Unprocessable Entity)
  await test('Creating project with empty name returns 422', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: tokenUserA
      },
      body: JSON.stringify({ name: '   ' })
    });

    assert.strictEqual(res.status, 422);
  });

  // 5. Retrieve Project by ID and by Slug
  await test('Get project by numeric ID', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, createdProjectId);
    assert.strictEqual(data.slug, 'ecommerce-seo');
  });

  await test('Get project by slug identifier', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectSlug}`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, createdProjectId);
    assert.strictEqual(data.slug, 'ecommerce-seo');
  });

  // 6. Update Project Details
  await test('Update project name and description', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: tokenUserA
      },
      body: JSON.stringify({
        name: 'Global E-Commerce SEO Campaign',
        description: 'Expanded global SEO optimization'
      })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.name, 'Global E-Commerce SEO Campaign');
    assert.strictEqual(data.description, 'Expanded global SEO optimization');
  });

  // 7. Settings, Metadata, Stats, and Activity Endpoints
  await test('Get and update project settings', async () => {
    const getRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}/settings`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(getRes.status, 200);

    const putRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: tokenUserA
      },
      body: JSON.stringify({
        settings: { crawl_frequency: 'weekly', max_depth: 5, alert_email: 'seo@company.com' }
      })
    });
    assert.strictEqual(putRes.status, 200);
    const updatedData = await putRes.json();
    assert.strictEqual(updatedData.settings.alert_email, 'seo@company.com');
  });

  await test('Get project metadata', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}/metadata`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const meta = await res.json();
    assert.strictEqual(meta.project_id, createdProjectId);
    assert.strictEqual(meta.slug, 'ecommerce-seo');
    assert.strictEqual(meta.settings_count, 3);
  });

  await test('Get project statistics', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}/stats`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const stats = await res.json();
    assert.strictEqual(stats.project_id, createdProjectId);
    assert.strictEqual(stats.settings_keys_count, 3);
  });

  await test('Get project activity audit log', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}/activity`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const activity = await res.json();
    assert(Array.isArray(activity));
  });

  // 8. Archive and Restore Lifecycle
  await test('Archive project', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}/archive`, {
      method: 'POST',
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.archived, true);
    assert.strictEqual(data.status, 'archived');
  });

  await test('Restore archived project', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}/restore`, {
      method: 'POST',
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.archived, false);
    assert.strictEqual(data.status, 'active');
  });

  // 9. Search and Filter Projects
  await test('Search projects by query', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects?search=Global`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);
    const list = await res.json();
    assert(Array.isArray(list));
    assert(list.some((p: any) => p.id === createdProjectId));
  });

  // 10. Delete Project
  await test('Delete project', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}`, {
      method: 'DELETE',
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(res.status, 200);

    const getRes = await fetch(`${baseUrl}/api/v1/orgs/${orgId}/projects/${createdProjectId}`, {
      headers: { Authorization: tokenUserA }
    });
    assert.strictEqual(getRes.status, 404);
  });

  await stopTestServer();

  console.log('\n==================================================');
  console.log(`Project Management Test Suite Summary:`);
  console.log(` Total Tests: ${passedCount + failedCount}`);
  console.log(` Passed:      ${passedCount}`);
  console.log(` Failed:      ${failedCount}`);
  console.log('==================================================\n');

  if (failedCount > 0) {
    process.exit(1);
  }
  process.exit(0);
}

runTests();
