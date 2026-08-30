import http from 'http';
import assert from 'assert';
import { executeCrawlPipeline } from '../src/services/crawlPipeline';

process.env.NODE_ENV = 'test';

let mockServer: http.Server;
let mockServerUrl: string;

function startMockServer(): Promise<string> {
  return new Promise((resolve) => {
    mockServer = http.createServer((req, res) => {
      const url = req.url || '/';

      if (url === '/robots.txt') {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end(`User-agent: *\nAllow: /\nDisallow: /private/\nSitemap: ${mockServerUrl}/sitemap.xml\n`);
        return;
      }

      if (url === '/sitemap.xml') {
        res.writeHead(200, { 'Content-Type': 'application/xml' });
        res.end(`<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${mockServerUrl}/</loc>
  </url>
  <url>
    <loc>${mockServerUrl}/about</loc>
  </url>
</urlset>`);
        return;
      }

      if (url === '/' || url === '') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(`<!DOCTYPE html>
<html lang="en">
<head>
  <title>Mock Test Site Home</title>
  <meta name="description" content="A comprehensive end-to-end crawl testing page.">
  <link rel="canonical" href="${mockServerUrl}/">
  <script type="application/ld+json">
    { "malformed": JSON, "unclosed":
  </script>
</head>
<body>
  <h1>Welcome to the Test Website</h1>
  <p>This is a paragraph with content for testing word count.</p>
  <h2>Section 1</h2>
  <img src="/logo.png" alt="Company Logo" width="200" height="50">
  <img src="/hero.png" width="800" height="600">
  <a href="/about">About Us</a>
  <a href="/contact">Contact Page</a>
  <a href="/redirect-page">Redirect Me</a>
  <a href="/no-meta">No Meta Page</a>
  <a href="/private/secret">Secret Disallowed Page</a>
  <a href="https://external-example.com">External Partner</a>
</body>
</html>`);
        return;
      }

      if (url === '/about') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(`<!DOCTYPE html>
<html lang="en">
<head>
  <title>About Us</title>
  <meta name="description" content="Learn more about our mission.">
</head>
<body>
  <h1>About Us</h1>
  <p>Our company was founded in 2026.</p>
  <a href="/">Home</a>
  <a href="/broken-link">Broken Link</a>
</body>
</html>`);
        return;
      }

      if (url === '/contact') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(`<!DOCTYPE html>
<html lang="en">
<head>
  <title>Contact Us</title>
  <meta name="description" content="Reach out to us.">
</head>
<body>
  <h1>Contact Us</h1>
  <a href="/">Return Home</a>
</body>
</html>`);
        return;
      }

      if (url === '/redirect-page') {
        res.writeHead(301, { 'Location': '/contact' });
        res.end();
        return;
      }

      if (url === '/no-meta') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(`<!DOCTYPE html>
<html>
<body>
  <p>Missing title and meta description</p>
</body>
</html>`);
        return;
      }

      if (url === '/private/secret') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(`<html><head><title>Secret</title></head><body>Disallowed</body></html>`);
        return;
      }

      if (url === '/broken-link') {
        res.writeHead(404, { 'Content-Type': 'text/html' });
        res.end('<h1>404 Not Found</h1>');
        return;
      }

      if (url === '/slow-page') {
        setTimeout(() => {
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end('<h1>Slow</h1>');
        }, 1500);
        return;
      }

      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    });

    mockServer.listen(0, '127.0.0.1', () => {
      const addr = mockServer.address() as any;
      mockServerUrl = `http://127.0.0.1:${addr.port}`;
      resolve(mockServerUrl);
    });
  });
}

function stopMockServer(): Promise<void> {
  return new Promise((resolve) => {
    if (mockServer) {
      mockServer.close(() => resolve());
    } else {
      resolve();
    }
  });
}

async function runTests() {
  console.log('🚀 Starting Crawl Pipeline End-to-End Test Suite...\n');
  mockServerUrl = await startMockServer();
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

  await test('1. Execute full crawl pipeline on mock site', async () => {
    const result = await executeCrawlPipeline(mockServerUrl, {
      maxDepth: 3,
      maxPages: 10,
      timeoutMs: 5000,
      allowLocalIp: true
    });

    assert.strictEqual(result.status, 'completed');
    assert.strictEqual(result.robotsTxtFound, true);
    assert.ok(result.sitemapsFound.length > 0);
    assert.ok(result.pages.length >= 3, `Expected at least 3 pages, got ${result.pages.length}`);

    // Verify Home Page crawled and extracted data
    const homePage = result.pages.find((p) => p.url === `${mockServerUrl}/` || p.url === mockServerUrl);
    assert.ok(homePage, 'Home page must be crawled');
    assert.strictEqual(homePage?.title, 'Mock Test Site Home');
    assert.strictEqual(homePage?.metaDescription, 'A comprehensive end-to-end crawl testing page.');
    assert.strictEqual(homePage?.h1, 'Welcome to the Test Website');
    assert.ok(homePage?.wordCount && homePage.wordCount > 5);

    // Verify Headings Extraction
    assert.strictEqual(homePage?.headings.counts.h1, 1);
    assert.strictEqual(homePage?.headings.counts.h2, 1);

    // Verify Image Extraction (found alt issue on hero.png)
    assert.strictEqual(homePage?.images.totalImages, 2);
    assert.strictEqual(homePage?.images.missingAltCount, 1);

    // Verify Link Graph
    assert.ok(result.linkGraphSummary.totalNodes >= 3);
    assert.ok(result.linkGraphSummary.totalEdges >= 3);
    assert.ok(result.linkGraphSummary.externalEdgesCount >= 1);

    // Verify Issue Detection
    const missingAltIssue = result.issues.find((i) => i.message.includes('missing alt attributes'));
    assert.ok(missingAltIssue, 'Should detect missing alt attributes issue');

    const brokenLinkIssue = result.issues.find((i) => i.pageUrl.includes('/broken-link'));
    assert.ok(brokenLinkIssue, 'Should detect 404 broken link issue');

    // Verify Robots-disallowed path was blocked from discovery
    const secretPage = result.pages.find((p) => p.url.includes('/private/secret'));
    assert.strictEqual(secretPage, undefined, 'Robots-disallowed page should not be crawled');

    // Verify No-Meta page produced missing title and description issues
    const missingTitleIssue = result.issues.find((i) => i.message.includes('missing a <title>'));
    assert.ok(missingTitleIssue, 'Should detect missing title issue');

    const missingMetaDescIssue = result.issues.find((i) => i.message.includes('missing a meta description'));
    assert.ok(missingMetaDescIssue, 'Should detect missing meta description issue');
  });

  await test('2. Max Pages and Max Depth Limits Enforcement', async () => {
    const result = await executeCrawlPipeline(mockServerUrl, {
      maxDepth: 0,
      maxPages: 1,
      timeoutMs: 3000,
      allowLocalIp: true
    });

    assert.strictEqual(result.pages.length, 1);
  });

  await test('3. Individual Failed Page does not crash crawl pipeline', async () => {
    const result = await executeCrawlPipeline(`${mockServerUrl}/broken-link`, {
      maxDepth: 1,
      maxPages: 5,
      timeoutMs: 3000,
      allowLocalIp: true
    });

    assert.strictEqual(result.status, 'completed');
    assert.ok(result.issues.length >= 1);
  });

  await stopMockServer();

  console.log(`\n========================================`);
  console.log(`Pipeline Test Results: ${passedCount} passed, ${failedCount} failed`);
  console.log(`========================================\n`);

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests().catch((err) => {
  console.error('Fatal Pipeline Test Runner Error:', err);
  process.exit(1);
});
