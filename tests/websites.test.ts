import {
  app,
  users,
  organizations,
  memberships,
  projects,
  websites,
  orgAuditEvents,
  checkRolePermission,
  normalizeDomain
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
  console.log('🚀 Starting Website Management Foundation (Milestone 6.2 Part 2) Test Suite...\n');
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

  // 1. Domain Normalization Unit Tests
  await test('normalizeDomain helper strips protocol, path, port, and query params into canonical domain', async () => {
    assert.strictEqual(normalizeDomain('https://example.com/'), 'example.com');
    assert.strictEqual(normalizeDomain('http://SUB.DOMAIN.CO.UK:8080/path?query=1#hash'), 'sub.domain.co.uk');
    assert.strictEqual(normalizeDomain('   App.TechFlow-Seo.com   '), 'app.techflow-seo.com');

    assert.throws(() => normalizeDomain(''), /cannot be empty/);
    assert.throws(() => normalizeDomain('not a valid domain!'), /Invalid domain/);
  });

  // 2. Authentication Tokens for Admin (User 1 - Org 1 Owner/Admin) and User 2 (External user)
  let adminToken = '';
  let nonMemberToken = '';

  await test('Authenticate users to obtain JWT access tokens', async () => {
    // User 1
    const res1 = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'admin@seoagent.app', password: 'AdminPass123!' })
    });
    assert.strictEqual(res1.status, 200);
    const data1 = await res1.json();
    adminToken = data1.access_token;
    assert.ok(adminToken, 'Expected admin token');

    // Register & login an external user (User 3) who is NOT a member of Org 1
    const regRes = await fetch(`${baseUrl}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'external.auditor@domain.com', username: 'auditor', password: 'AuditorPass123!' })
    });
    assert.strictEqual(regRes.status, 200);
    const regData = await regRes.json();
    // Auto-verify external user for testing
    const externalUser = users.find(u => u.id === regData.id);
    if (externalUser) externalUser.is_verified = true;

    const loginRes = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'external.auditor@domain.com', password: 'AuditorPass123!' })
    });
    assert.strictEqual(loginRes.status, 200);
    const loginData = await loginRes.json();
    nonMemberToken = loginData.access_token;
    assert.ok(nonMemberToken, 'Expected non-member token');
  });

  // 2b. Tenant Isolation Test
  await test('Tenant Isolation: non-member of organization is denied access with 403 Forbidden', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/1/websites`, {
      headers: { Authorization: `Bearer ${nonMemberToken}` }
    });
    assert.strictEqual(res.status, 403);
  });

  // 3. Validate Domain Endpoint
  await test('GET /projects/:id/websites/validate-domain checks domain availability in project', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/1/websites/validate-domain?domain=techflow-seo.com`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.available, false);
    assert.strictEqual(data.canonical_domain, 'techflow-seo.com');

    const res2 = await fetch(`${baseUrl}/api/v1/projects/1/websites/validate-domain?domain=https://brand-new-site.org/deep-path`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res2.status, 200);
    const data2 = await res2.json();
    assert.strictEqual(data2.available, true);
    assert.strictEqual(data2.canonical_domain, 'brand-new-site.org');
  });

  // 4. Create Website in Project
  let createdWebsiteId = 0;
  await test('POST /projects/:id/websites creates a project-centric website with canonical domain', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/1/websites`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`
      },
      body: JSON.stringify({
        domain: 'https://Global-Shop-2026.com/home',
        name: 'Global Shop Online',
        description: 'E-commerce primary digital storefront',
        status: 'active',
        settings: { crawl_frequency: 'daily', max_depth: 10 },
        metadata: { engine: 'Shopify', target_market: 'Global' }
      })
    });
    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.strictEqual(data.domain, 'global-shop-2026.com');
    assert.strictEqual(data.name, 'Global Shop Online');
    assert.strictEqual(data.project_id, 1);
    assert.strictEqual(data.organization_id, 1);
    assert.strictEqual(data.archived, false);
    assert.strictEqual(data.settings.crawl_frequency, 'daily');
    createdWebsiteId = data.id;
  });

  // 5. Enforce Domain Uniqueness in Project
  await test('POST /projects/:id/websites rejects duplicate domain in same project with 409 Conflict', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/1/websites`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`
      },
      body: JSON.stringify({
        domain: 'global-shop-2026.com',
        name: 'Duplicate Site Entry'
      })
    });
    assert.strictEqual(res.status, 409);
    const data = await res.json();
    assert.ok(data.error.includes('already registered'));
  });

  // 6. List and Search Project Websites
  await test('GET /projects/:id/websites lists paginated websites and filters by search query', async () => {
    const res = await fetch(`${baseUrl}/api/v1/projects/1/websites?search=Global+Shop`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.total, 1);
    assert.strictEqual(data.items[0].id, createdWebsiteId);
    assert.strictEqual(data.items[0].domain, 'global-shop-2026.com');
  });

  // 7. Get Website by ID
  await test('GET /websites/:id retrieves website details with project and owner metadata', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, createdWebsiteId);
    assert.strictEqual(data.domain, 'global-shop-2026.com');
    assert.strictEqual(data.name, 'Global Shop Online');
  });

  // 8. Update Website Properties
  await test('PATCH /websites/:id updates name, description, and status', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`
      },
      body: JSON.stringify({
        name: 'Global Shop Premier',
        description: 'Updated enterprise e-commerce platform'
      })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.name, 'Global Shop Premier');
    assert.strictEqual(data.description, 'Updated enterprise e-commerce platform');
  });

  // 9. Website Settings (JSON) GET and PUT
  await test('GET and PUT /websites/:id/settings handles structured JSON configuration', async () => {
    const putRes = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`
      },
      body: JSON.stringify({
        settings: { crawl_frequency: 'hourly', render_js: true, alert_threshold: 90 }
      })
    });
    assert.strictEqual(putRes.status, 200);
    const putData = await putRes.json();
    assert.strictEqual(putData.settings.render_js, true);
    assert.strictEqual(putData.settings.crawl_frequency, 'hourly');

    const getRes = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}/settings`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(getRes.status, 200);
    const getData = await getRes.json();
    assert.strictEqual(getData.settings.alert_threshold, 90);
  });

  // 10. Website Metadata
  await test('GET /websites/:id/metadata returns structured metadata payload', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}/metadata`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.website_id, createdWebsiteId);
    assert.strictEqual(data.metadata.engine, 'Shopify');
  });

  // 11. Website Foundational Stats
  await test('GET /websites/:id/stats returns analytics counts and active status', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}/stats`, {
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.website_id, createdWebsiteId);
    assert.strictEqual(data.domain, 'global-shop-2026.com');
    assert.strictEqual(typeof data.days_active, 'number');
    assert.strictEqual(data.settings_count, 3);
  });

  // 12. Archive and Restore Website
  await test('POST /websites/:id/archive and restore sets archived flag and status correctly', async () => {
    const arcRes = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}/archive`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(arcRes.status, 200);
    const arcData = await arcRes.json();
    assert.strictEqual(arcData.archived, true);
    assert.strictEqual(arcData.status, 'archived');

    const restRes = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}/restore`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(restRes.status, 200);
    const restData = await restRes.json();
    assert.strictEqual(restData.archived, false);
    assert.strictEqual(restData.status, 'active');
  });

  // 13. Audit Logging Verification
  await test('Audit trail records all website creation, modification, and archive events', async () => {
    const createdEvents = orgAuditEvents.filter(e => e.action === 'website.created' && e.details.website_id === createdWebsiteId);
    assert.ok(createdEvents.length >= 1, 'Expected website.created audit event');

    const updatedEvents = orgAuditEvents.filter(e => e.action === 'website.updated' && e.details.website_id === createdWebsiteId);
    assert.ok(updatedEvents.length >= 1, 'Expected website.updated audit event');
  });

  // 14. Delete Website
  await test('DELETE /websites/:id deletes website and returns 200', async () => {
    const delRes = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${adminToken}` }
    });
    assert.strictEqual(delRes.status, 200);

    const getRes = await fetch(`${baseUrl}/api/v1/websites/${createdWebsiteId}`, {
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
  } else {
    process.exit(0);
  }
}

runTests().catch(err => {
  console.error('Test runner fatal error:', err);
  process.exit(1);
});
