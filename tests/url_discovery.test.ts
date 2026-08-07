import { app } from '../server';
import { URLDiscoveryManager } from '../src/services/urlDiscoveryManager';
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
  console.log('🔍 Starting URL Discovery & Crawl Queue Management Test Suite...\n');
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

  // --- 1. UNIT TESTS FOR URL DISCOVERY MANAGER SERVICE ---
  await test('URLDiscoveryManager - Auto-enqueue seed URL in Queue state', async () => {
    const manager = new URLDiscoveryManager('test-1', 'https://example.com');
    const stats = manager.getStats();

    assert.strictEqual(stats.totalDiscovered, 1);
    assert.strictEqual(stats.queueCount, 1);
    assert.strictEqual(stats.pendingCount, 0);
    assert.strictEqual(stats.visitedCount, 0);
    assert.strictEqual(stats.failedCount, 0);
  });

  await test('URLDiscoveryManager - State Transitions: Queue -> Pending -> Visited', async () => {
    const manager = new URLDiscoveryManager('test-2', 'https://example.com');

    // Dequeue item
    const item = manager.next();
    assert.ok(item);
    assert.strictEqual(item!.url, 'https://example.com');
    assert.strictEqual(item!.status, 'pending');
    assert.strictEqual(item!.attempts, 1);

    let stats = manager.getStats();
    assert.strictEqual(stats.queueCount, 0);
    assert.strictEqual(stats.pendingCount, 1);

    // Mark visited
    const visitedOk = manager.markVisited('https://example.com', 200, 0);
    assert.strictEqual(visitedOk, true);

    stats = manager.getStats();
    assert.strictEqual(stats.pendingCount, 0);
    assert.strictEqual(stats.visitedCount, 1);
  });

  await test('URLDiscoveryManager - Configurable Retry & Failed State Transition', async () => {
    const manager = new URLDiscoveryManager('test-3', 'https://example.com', { retry: 2 });

    // Attempt 1 fails -> re-queued
    let item = manager.next();
    assert.ok(item);
    assert.strictEqual(item!.attempts, 1);

    manager.markFailed('https://example.com', 'Timeout 504');
    let stats = manager.getStats();
    assert.strictEqual(stats.queueCount, 1);
    assert.strictEqual(stats.failedCount, 0);

    // Attempt 2 fails -> reaches retry max limit (2) -> moved to Failed
    item = manager.next();
    assert.ok(item);
    assert.strictEqual(item!.attempts, 2);

    manager.markFailed('https://example.com', 'Connection refused');
    stats = manager.getStats();
    assert.strictEqual(stats.queueCount, 0);
    assert.strictEqual(stats.pendingCount, 0);
    assert.strictEqual(stats.failedCount, 1);
  });

  await test('URLDiscoveryManager - Enforce Max Depth limit', async () => {
    const manager = new URLDiscoveryManager('test-4', 'https://example.com', { maxDepth: 1 });

    // Depth 1 -> Accepted
    const added1 = manager.enqueue('https://example.com/depth-1', 1);
    assert.strictEqual(added1, true);

    // Depth 2 -> Exceeds maxDepth (1), Rejected
    const added2 = manager.enqueue('https://example.com/depth-2', 2);
    assert.strictEqual(added2, false);

    assert.strictEqual(manager.getStats().queueCount, 2); // Seed (0) + Depth 1
  });

  await test('URLDiscoveryManager - Enforce Max Pages limit', async () => {
    const manager = new URLDiscoveryManager('test-5', 'https://example.com', { maxPages: 2 });

    // Seed is page 1
    assert.strictEqual(manager.getStats().totalDiscovered, 1);

    // Add 1 page -> total 2 -> Accepted
    const added1 = manager.enqueue('https://example.com/page-2', 1);
    assert.strictEqual(added1, true);

    // Add 1 more page -> total would be 3 > maxPages (2) -> Rejected
    const added2 = manager.enqueue('https://example.com/page-3', 1);
    assert.strictEqual(added2, false);

    assert.strictEqual(manager.getStats().totalDiscovered, 2);
  });

  // --- 2. REST API ENDPOINT TESTS ---
  let sessionId = '';

  await test('POST /api/v1/url-discovery/sessions - Create session with custom limits', async () => {
    const res = await fetch(`${baseUrl}/api/v1/url-discovery/sessions`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        seedUrl: 'https://mysite.com',
        maxDepth: 2,
        maxPages: 5,
        maxRedirects: 3,
        timeout: 5000,
        retry: 2
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();

    assert.ok(data.sessionId);
    assert.strictEqual(data.seedUrl, 'https://mysite.com');
    assert.strictEqual(data.config.maxDepth, 2);
    assert.strictEqual(data.config.maxPages, 5);
    assert.strictEqual(data.config.maxRedirects, 3);
    assert.strictEqual(data.config.timeout, 5000);
    assert.strictEqual(data.config.retry, 2);
    assert.strictEqual(data.stats.queueCount, 1);

    sessionId = data.sessionId;
  });

  await test('POST /api/v1/url-discovery/sessions/:id/enqueue - Enqueue discovered URLs', async () => {
    const res = await fetch(`${baseUrl}/api/v1/url-discovery/sessions/${sessionId}/enqueue`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        urls: [
          '/about',
          '/contact',
          'https://mysite.com/blog'
        ],
        currentDepth: 0,
        sourceUrl: 'https://mysite.com'
      })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.addedCount, 3);
    assert.strictEqual(data.stats.queueCount, 4); // Seed + 3 discovered
  });

  await test('POST /api/v1/url-discovery/sessions/:id/next - Dequeue next URL', async () => {
    const res = await fetch(`${baseUrl}/api/v1/url-discovery/sessions/${sessionId}/next`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.ok(data.item);
    assert.strictEqual(data.item.url, 'https://mysite.com');
    assert.strictEqual(data.item.status, 'pending');
    assert.strictEqual(data.stats.pendingCount, 1);
  });

  await test('POST /api/v1/url-discovery/sessions/:id/mark-visited - Mark URL as Visited', async () => {
    const res = await fetch(`${baseUrl}/api/v1/url-discovery/sessions/${sessionId}/mark-visited`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: 'https://mysite.com',
        statusCode: 200,
        redirectCount: 0
      })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.success, true);
    assert.strictEqual(data.stats.visitedCount, 1);
    assert.strictEqual(data.stats.pendingCount, 0);
  });

  await test('GET /api/v1/url-discovery/sessions/:id/urls - Query URLs by Queue/Visited/Failed state', async () => {
    const resVisited = await fetch(`${baseUrl}/api/v1/url-discovery/sessions/${sessionId}/urls?status=visited`, {
      headers: { 'Authorization': tokenUser }
    });
    assert.strictEqual(resVisited.status, 200);
    const dataVisited = await resVisited.json();
    assert.strictEqual(dataVisited.total, 1);
    assert.strictEqual(dataVisited.items[0].url, 'https://mysite.com');

    const resQueue = await fetch(`${baseUrl}/api/v1/url-discovery/sessions/${sessionId}/urls?status=queue`, {
      headers: { 'Authorization': tokenUser }
    });
    assert.strictEqual(resQueue.status, 200);
    const dataQueue = await resQueue.json();
    assert.strictEqual(dataQueue.total, 3);
  });

  console.log(`\n🎉 URL Discovery Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
