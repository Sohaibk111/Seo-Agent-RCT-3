import { app } from '../server';
import { LinkGraphManager } from '../src/services/linkGraphManager';
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
  console.log('🔗 Starting Internal Link Graph Test Suite...\n');
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

  // --- 1. UNIT TESTS FOR LINK GRAPH MANAGER ---

  await test('LinkGraphManager - Add Pages and Internal vs External Link classification', async () => {
    const manager = new LinkGraphManager('g1', 'https://example.com');

    // Add Internal Link (Page A -> Page B)
    manager.addLink('https://example.com/page-a', 'https://example.com/page-b', 'Page B');

    // Add External Link (Page A -> Google)
    manager.addLink('https://example.com/page-a', 'https://google.com', 'Google Search', 'nofollow');

    const internalLinks = manager.getInternalLinks();
    const externalLinks = manager.getExternalLinks();

    assert.strictEqual(internalLinks.length, 1);
    assert.strictEqual(internalLinks[0].targetUrl, 'https://example.com/page-b');
    assert.strictEqual(externalLinks.length, 1);
    assert.strictEqual(externalLinks[0].targetUrl, 'https://google.com');
  });

  await test('LinkGraphManager - Detect Broken Links (status >= 400)', async () => {
    const manager = new LinkGraphManager('g2', 'https://example.com');

    // Add healthy page and broken 404 target page
    manager.addPage('https://example.com/broken-page', 404);
    manager.addLink('https://example.com/home', 'https://example.com/broken-page', 'Broken Link');

    const brokenLinks = manager.getBrokenLinks();
    assert.strictEqual(brokenLinks.length, 1);
    assert.strictEqual(brokenLinks[0].targetUrl, 'https://example.com/broken-page');
  });

  await test('LinkGraphManager - Detect Orphan Pages (0 inbound internal links)', async () => {
    const manager = new LinkGraphManager('g3', 'https://example.com');

    // Home links to Page A
    manager.addLink('https://example.com', 'https://example.com/page-a', 'Page A');

    // Page B is registered but has NO inbound links
    manager.addPage('https://example.com/orphan-b', 200);

    const orphans = manager.getOrphanPages();
    assert.strictEqual(orphans.length, 1);
    assert.strictEqual(orphans[0].url, 'https://example.com/orphan-b');
  });

  await test('LinkGraphManager - Detect Redirect Chains (Page A -> Page B -> Page C)', async () => {
    const manager = new LinkGraphManager('g4', 'https://example.com');

    // Setup redirect sequence: /old-1 (301 -> /old-2) -> /old-2 (301 -> /final) -> /final (200)
    manager.addPage('https://example.com/old-1', 301, 'https://example.com/old-2');
    manager.addPage('https://example.com/old-2', 301, 'https://example.com/final');
    manager.addPage('https://example.com/final', 200);

    const chains = manager.getRedirectChains();
    assert.strictEqual(chains.length, 2); // /old-1 has chain of 2 hops, /old-2 has chain of 1 hop

    const mainChain = chains.find(c => c.startUrl === 'https://example.com/old-1');
    assert.ok(mainChain);
    assert.strictEqual(mainChain!.hopCount, 2);
    assert.deepStrictEqual(mainChain!.chain, [
      'https://example.com/old-1',
      'https://example.com/old-2',
      'https://example.com/final'
    ]);
    assert.strictEqual(mainChain!.finalUrl, 'https://example.com/final');
    assert.strictEqual(mainChain!.finalStatusCode, 200);
  });

  // --- 2. REST API ENDPOINT TESTS ---

  let graphId = '';

  await test('POST /api/v1/link-graph/graphs - Create graph session', async () => {
    const res = await fetch(`${baseUrl}/api/v1/link-graph/graphs`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        baseUrl: 'https://mywebsite.com'
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.ok(data.graphId);
    assert.strictEqual(data.baseUrl, 'https://mywebsite.com');
    assert.strictEqual(data.summary.totalNodes, 0);

    graphId = data.graphId;
  });

  await test('POST /api/v1/link-graph/graphs/:id/pages - Populate pages with status codes', async () => {
    // Add page A
    await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: 'https://mywebsite.com/page-a', statusCode: 200 })
    });

    // Add page B (404)
    await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: 'https://mywebsite.com/missing-b', statusCode: 404 })
    });

    // Add page C (Orphan)
    await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: 'https://mywebsite.com/orphan-c', statusCode: 200 })
    });

    // Add page D (Redirect 301 -> /page-a)
    await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/pages`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: 'https://mywebsite.com/redirect-d', statusCode: 301, redirectTarget: 'https://mywebsite.com/page-a' })
    });

    const res = await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}`, {
      headers: { 'Authorization': tokenUser }
    });
    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.summary.totalNodes, 4);
  });

  await test('POST /api/v1/link-graph/graphs/:id/links - Create internal and external link edges', async () => {
    // Page A -> missing B (Broken internal)
    await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/links`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ sourceUrl: 'https://mywebsite.com/page-a', targetUrl: 'https://mywebsite.com/missing-b', anchorText: 'Missing B' })
    });

    // Page A -> External site
    await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/links`, {
      method: 'POST',
      headers: { 'Authorization': tokenUser, 'Content-Type': 'application/json' },
      body: JSON.stringify({ sourceUrl: 'https://mywebsite.com/page-a', targetUrl: 'https://external-site.org/docs', anchorText: 'External Docs' })
    });

    const res = await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}`, {
      headers: { 'Authorization': tokenUser }
    });
    const data = await res.json();
    assert.strictEqual(data.summary.totalEdges, 2);
    assert.strictEqual(data.summary.internalEdgesCount, 1);
    assert.strictEqual(data.summary.externalEdgesCount, 1);
  });

  await test('GET endpoints - Query Broken Links, Orphan Pages, and Redirect Chains', async () => {
    // Broken Links
    const resBroken = await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/broken-links`, {
      headers: { 'Authorization': tokenUser }
    });
    assert.strictEqual(resBroken.status, 200);
    const dataBroken = await resBroken.json();
    assert.strictEqual(dataBroken.total, 1);
    assert.strictEqual(dataBroken.links[0].targetUrl, 'https://mywebsite.com/missing-b');

    // Orphan Pages
    const resOrphans = await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/orphan-pages`, {
      headers: { 'Authorization': tokenUser }
    });
    assert.strictEqual(resOrphans.status, 200);
    const dataOrphans = await resOrphans.json();
    assert.ok(dataOrphans.total >= 1);
    const orphanC = dataOrphans.orphans.find((o: any) => o.url === 'https://mywebsite.com/orphan-c');
    assert.ok(orphanC);

    // Redirect Chains
    const resChains = await fetch(`${baseUrl}/api/v1/link-graph/graphs/${graphId}/redirect-chains`, {
      headers: { 'Authorization': tokenUser }
    });
    assert.strictEqual(resChains.status, 200);
    const dataChains = await resChains.json();
    assert.strictEqual(dataChains.total, 1);
    assert.strictEqual(dataChains.redirectChains[0].startUrl, 'https://mywebsite.com/redirect-d');
  });

  console.log(`\n🎉 Internal Link Graph Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
