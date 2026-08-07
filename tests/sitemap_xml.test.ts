import { app } from '../server';
import { parseSitemapXml, discoverSitemapCandidateUrls } from '../src/services/sitemapParser';
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
  console.log('🗺️ Starting Sitemap XML Parsing & Discovery Test Suite...\n');
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

  const sampleUrlsetXml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url>
    <loc>https://example.com/page1</loc>
    <lastmod>2026-08-01</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
    <image:image>
      <image:loc>https://example.com/images/hero.jpg</image:loc>
      <image:title>Hero Image Title</image:title>
      <image:caption>Hero Image Caption</image:caption>
    </image:image>
  </url>
  <url>
    <loc>https://example.com/page2</loc>
    <lastmod>2026-08-02</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
</urlset>`;

  const sampleIndexXml = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-posts.xml</loc>
    <lastmod>2026-08-05</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-products.xml</loc>
    <lastmod>2026-08-06</lastmod>
  </sitemap>
</sitemapindex>`;

  const tokenUser = 'Bearer token_user_1';

  // --- 1. SERVICE UNIT TESTS ---
  await test('discoverSitemapCandidateUrls - Auto discover /sitemap.xml and /sitemap_index.xml', async () => {
    const candidates = discoverSitemapCandidateUrls('https://example.com/blog/article-1');
    assert.deepStrictEqual(candidates, [
      'https://example.com/sitemap.xml',
      'https://example.com/sitemap_index.xml'
    ]);
  });

  await test('discoverSitemapCandidateUrls - Deduplicate robots.txt sitemaps', async () => {
    const robotsSitemaps = [
      'https://example.com/custom-sitemap.xml',
      'https://example.com/sitemap.xml'
    ];
    const candidates = discoverSitemapCandidateUrls('https://example.com', robotsSitemaps);

    assert.strictEqual(candidates.length, 3);
    assert.strictEqual(candidates[0], 'https://example.com/custom-sitemap.xml');
    assert.strictEqual(candidates[1], 'https://example.com/sitemap.xml');
    assert.strictEqual(candidates[2], 'https://example.com/sitemap_index.xml');
  });

  await test('parseSitemapXml - Parse standard urlset with image sitemaps', async () => {
    const result = parseSitemapXml(sampleUrlsetXml);

    assert.strictEqual(result.isIndex, false);
    assert.strictEqual(result.totalUrls, 2);
    assert.strictEqual(result.totalImages, 1);

    assert.strictEqual(result.urls[0].loc, 'https://example.com/page1');
    assert.strictEqual(result.urls[0].lastmod, '2026-08-01');
    assert.strictEqual(result.urls[0].changefreq, 'daily');
    assert.strictEqual(result.urls[0].priority, 0.8);
    assert.strictEqual(result.urls[0].images.length, 1);
    assert.strictEqual(result.urls[0].images[0].loc, 'https://example.com/images/hero.jpg');
    assert.strictEqual(result.urls[0].images[0].title, 'Hero Image Title');
    assert.strictEqual(result.urls[0].images[0].caption, 'Hero Image Caption');

    assert.strictEqual(result.urls[1].loc, 'https://example.com/page2');
    assert.strictEqual(result.urls[1].priority, 0.5);
  });

  await test('parseSitemapXml - Parse nested sitemap index', async () => {
    const result = parseSitemapXml(sampleIndexXml);

    assert.strictEqual(result.isIndex, true);
    assert.strictEqual(result.childSitemaps.length, 2);
    assert.strictEqual(result.childSitemaps[0].loc, 'https://example.com/sitemap-posts.xml');
    assert.strictEqual(result.childSitemaps[0].lastmod, '2026-08-05');
    assert.strictEqual(result.childSitemaps[1].loc, 'https://example.com/sitemap-products.xml');
  });

  // --- 2. API ENDPOINT TESTS ---
  await test('POST /api/v1/parse-sitemap - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-sitemap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ xml: sampleUrlsetXml })
    });
    assert.strictEqual(res.status, 401);
  });

  await test('POST /api/v1/parse-sitemap - Parse sitemap XML payload', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-sitemap`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ xml: sampleUrlsetXml })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.isIndex, false);
    assert.strictEqual(data.totalUrls, 2);
    assert.strictEqual(data.totalImages, 1);
  });

  await test('POST /api/v1/discover-sitemaps - Return discovered sitemap candidates', async () => {
    const res = await fetch(`${baseUrl}/api/v1/discover-sitemaps`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        baseUrl: 'https://example.com',
        robotsSitemaps: ['https://example.com/special-sitemap.xml']
      })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.baseUrl, 'https://example.com');
    assert.deepStrictEqual(data.discoveredCandidates, [
      'https://example.com/special-sitemap.xml',
      'https://example.com/sitemap.xml',
      'https://example.com/sitemap_index.xml'
    ]);
  });

  console.log(`\n🎉 Sitemap XML Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
