import { app, websites, auditResults, leads, reports, users } from '../server';
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
  console.log('🚀 Starting Authorization & Multi-Tenant Security Test Suite...\n');
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

  // Tokens
  const userAToken = 'Bearer token_user_1'; // Admin / User A (id: 1)
  const userBToken = 'Bearer token_user_2'; // User B (id: 2)

  // 1. Unauthenticated Security Tests (401)
  await test('Unauthenticated GET /api/v1/websites returns 401', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites`);
    assert.strictEqual(res.status, 401);
    const body = await res.json();
    assert.strictEqual(body.error, 'Unauthorized');
  });

  await test('Unauthenticated GET /api/v1/auth/me returns 401', async () => {
    const res = await fetch(`${baseUrl}/api/v1/auth/me`);
    assert.strictEqual(res.status, 401);
  });

  await test('Unauthenticated POST /api/v1/audit returns 401', async () => {
    const res = await fetch(`${baseUrl}/api/v1/audit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: 'https://test-unauth.com' })
    });
    assert.strictEqual(res.status, 401);
  });

  // 2. Resource Ownership & Authenticated Access for User A
  let userAWebsiteId: number = 1;
  await test('User A can list their owned websites', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites`, {
      headers: { Authorization: userAToken }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert(Array.isArray(data));
    assert(data.some((w: any) => w.id === 1));
  });

  await test('User A creates website and audit', async () => {
    const res = await fetch(`${baseUrl}/api/v1/audit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: userAToken
      },
      body: JSON.stringify({ url: 'https://usera-exclusive.com' })
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    userAWebsiteId = data.website.id;
    assert.strictEqual(data.website.user_id, 1);
  });

  // 3. Multi-Tenant Authorization Isolation Tests for User B (403 Forbidden)
  await test('User B cannot read User A website (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/${userAWebsiteId}`, {
      headers: { Authorization: userBToken }
    });
    assert.strictEqual(res.status, 403);
    const data = await res.json();
    assert(data.error.includes('Forbidden'));
  });

  await test('User B cannot audit User A website by website_id (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/audit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: userBToken
      },
      body: JSON.stringify({ website_id: userAWebsiteId })
    });
    assert.strictEqual(res.status, 403);
  });

  await test('User B cannot audit User A domain directly (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/audit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: userBToken
      },
      body: JSON.stringify({ url: 'https://usera-exclusive.com' })
    });
    assert.strictEqual(res.status, 403);
  });

  await test('User B cannot export User A report (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/reports/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: userBToken
      },
      body: JSON.stringify({ website_id: userAWebsiteId, format: 'pdf' })
    });
    assert.strictEqual(res.status, 403);
  });

  await test('User B cannot delete User A website (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/${userAWebsiteId}`, {
      method: 'DELETE',
      headers: { Authorization: userBToken }
    });
    assert.strictEqual(res.status, 403);
  });

  await test('User B cannot request AI analysis for User A audit (403)', async () => {
    const auditId = auditResults.find(a => a.user_id === 1)?.id || 101;
    const res = await fetch(`${baseUrl}/api/v1/ai/analyze/${auditId}`, {
      headers: { Authorization: userBToken }
    });
    assert.strictEqual(res.status, 403);
  });

  await test('User B cannot check rank for User A website (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/rank/check`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: userBToken
      },
      body: JSON.stringify({ keyword: 'seo', domain: 'usera-exclusive.com' })
    });
    assert.strictEqual(res.status, 403);
  });

  await test('User B cannot access User A leads (403)', async () => {
    const res = await fetch(`${baseUrl}/api/v1/leads/${userAWebsiteId}`, {
      headers: { Authorization: userBToken }
    });
    assert.strictEqual(res.status, 403);
  });

  // 4. Non-Existent Resources (404 Not Found)
  await test('Request for non-existent website returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/999999`, {
      headers: { Authorization: userAToken }
    });
    assert.strictEqual(res.status, 404);
  });

  await test('Delete non-existent website returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/999999`, {
      method: 'DELETE',
      headers: { Authorization: userAToken }
    });
    assert.strictEqual(res.status, 404);
  });

  await test('AI analysis for non-existent audit returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/ai/analyze/999999`, {
      headers: { Authorization: userAToken }
    });
    assert.strictEqual(res.status, 404);
  });

  await test('Leads for non-existent website returns 404', async () => {
    const res = await fetch(`${baseUrl}/api/v1/leads/999999`, {
      headers: { Authorization: userAToken }
    });
    assert.strictEqual(res.status, 404);
  });

  // 5. Data Isolation & Deletion Regression Tests
  await test('User B list websites returns only User B resources', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites`, {
      headers: { Authorization: userBToken }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert(Array.isArray(data));
    assert(!data.some((w: any) => w.id === userAWebsiteId));
  });

  await test('User A can delete their own website', async () => {
    const res = await fetch(`${baseUrl}/api/v1/websites/${userAWebsiteId}`, {
      method: 'DELETE',
      headers: { Authorization: userAToken }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, userAWebsiteId);
  });

  await stopTestServer();

  console.log(`\n Total Tests: ${passedCount + failedCount}`);
  console.log(` Passed: ${passedCount}`);
  console.log(` Failed: ${failedCount}`);

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests().catch((err) => {
  console.error('Test runner exception:', err);
  process.exit(1);
});
