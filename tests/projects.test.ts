import {
  app,
  users,
  organizations,
  memberships,
  projects,
  orgAuditEvents,
  checkRolePermission,
  slugifyText
} from '../server';
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
  console.log('🚀 Starting Projects Foundation & RBAC Test Suite...\n');
  baseUrl = await startTestServer();
  let passedCount = 0;
  let failedCount = 0;

  async function test(name: string, fn: () => Promise<void>) {
    try {
      await fn();
      console.log(`  ✅ PASS: ${name}`);
      passedCount++;
    } catch (err: any) {
      console.error(`  ❌ FAIL: ${name}`);
      console.error(`     Error: ${err.message}`);
      failedCount++;
    }
  }

  // 1. Slugify utility
  await test('Slugify helper formats titles safely into URL slugs', async () => {
    assert.strictEqual(slugifyText('My New Global Project!'), 'my-new-global-project');
    assert.strictEqual(slugifyText('  SEO & Analytics 2026--- '), 'seo-analytics-2026');
  });

  // 2. Role Hierarchy
  await test('RBAC hierarchy accurately validates permissions', async () => {
    assert.strictEqual(checkRolePermission('Owner', 'Member'), true);
    assert.strictEqual(checkRolePermission('Admin', 'Manager'), true);
    assert.strictEqual(checkRolePermission('Manager', 'Admin'), false);
    assert.strictEqual(checkRolePermission('Viewer', 'Member'), false);
  });

  // 3. Login to get token for User 1 (Admin/Owner)
  let adminToken = '';
  await test('Authenticate as Admin/Owner to obtain JWT', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'admin@seoagent.app', password: 'AdminPass123!' })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    adminToken = data.access_token;
    assert.ok(adminToken, 'Expected access token');
  });

  // 4. Validate Slug Check
  await test('GET /orgs/:id/projects/validate-slug checks availability', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects/validate-slug?slug=e-commerce-expansion`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.available, false);

    const res2 = await fetch(`${baseUrl}/api/v1/orgs/1/projects/validate-slug?slug=brand-new-initiative`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res2.status, 200);
    const data2 = await res2.json();
    assert.strictEqual(data2.available, true);
  });

  // 5. Create Project
  let createdProjectId = 0;
  await test('POST /orgs/:id/projects creates a tenant-isolated project', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`
      },
      body: JSON.stringify({
        name: 'Omni-Channel Rank Tracker',
        slug: 'omni-channel-rank-tracker',
        description: 'Tracking desktop and mobile SERP signals',
        status: 'active',
        color: '#6366F1',
        icon: 'trending-up',
        timezone: 'America/New_York',
        language: 'en',
        settings: { crawl_frequency: 'daily' }
      })
    });
    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.strictEqual(data.name, 'Omni-Channel Rank Tracker');
    assert.strictEqual(data.slug, 'omni-channel-rank-tracker');
    assert.strictEqual(data.organization_id, 1);
    assert.strictEqual(data.archived, false);
    createdProjectId = data.id;
  });

  // 6. List & Search Projects
  await test('GET /orgs/:id/projects returns paginated projects and matches search queries', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects?search=Rank+Tracker`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 1);
    assert.strictEqual(data.items[0].id, createdProjectId);
  });

  // 7. Get Project by ID or Slug
  await test('GET /orgs/:id/projects/:project_id retrieves by ID or slug', async () => {
    const byId = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(byId.status, 200);

    const bySlug = await fetch(`${baseUrl}/api/v1/orgs/1/projects/omni-channel-rank-tracker`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(bySlug.status, 200);
    const data = await bySlug.json();
    assert.strictEqual(data.id, createdProjectId);
  });

  // 8. Update Project
  await test('PATCH /orgs/:id/projects/:project_id updates project properties', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`
      },
      body: JSON.stringify({
        description: 'Updated omni-channel description with deep audit',
        color: '#8B5CF6'
      })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.description, 'Updated omni-channel description with deep audit');
    assert.strictEqual(data.color, '#8B5CF6');
  });

  // 9. Update Settings
  await test('PUT /orgs/:id/projects/:project_id/settings updates settings json', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`
      },
      body: JSON.stringify({
        settings: { crawl_frequency: 'weekly', max_depth: 8, email_alerts: true }
      })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.settings.max_depth, 8);
  });

  // 10. Get Stats
  await test('GET /orgs/:id/projects/:project_id/stats returns analytics summary', async () => {
    const res = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}/stats`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.project_id, createdProjectId);
    assert.strictEqual(data.settings_count, 3);
  });

  // 11. Archive and Restore
  await test('POST /orgs/:id/projects/:project_id/archive and restore works smoothly', async () => {
    const arcRes = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}/archive`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(arcRes.status, 200);
    const arcData = await arcRes.json();
    assert.strictEqual(arcData.archived, true);
    assert.strictEqual(arcData.status, 'archived');

    const restRes = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}/restore`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(restRes.status, 200);
    const restData = await restRes.json();
    assert.strictEqual(restData.archived, false);
    assert.strictEqual(restData.status, 'active');
  });

  // 12. Delete Project
  await test('DELETE /orgs/:id/projects/:project_id removes project cleanly', async () => {
    const delRes = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(delRes.status, 200);

    const getRes = await fetch(`${baseUrl}/api/v1/orgs/1/projects/${createdProjectId}`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(getRes.status, 404);
  });

  await stopTestServer();
  console.log(`\n========================================`);
  console.log(`Results: ${passedCount} passed, ${failedCount} failed`);
  console.log(`========================================\n`);

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests().catch(err => {
  console.error('Test runner fatal error:', err);
  process.exit(1);
});
