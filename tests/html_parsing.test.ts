import { app } from '../server';
import { parseHtml } from '../src/services/htmlParser';
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
  console.log('📄 Starting HTML Parsing Infrastructure Test Suite...\n');
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

  const sampleHtml = `
    <!DOCTYPE html>
    <html lang="en-US">
    <head>
      <meta charset="UTF-8">
      <title>  SEO Agent Test Page  </title>
      <meta name="description" content="This is an automated test page for SEO auditing.">
      <meta name="robots" content="index, follow">
      <link rel="canonical" href="/canonical-page">
      
      <!-- Open Graph -->
      <meta property="og:title" content="OG Test Title">
      <meta property="og:description" content="OG Test Description">
      <meta property="og:image" content="https://example.com/og-image.png">
      
      <!-- Twitter Cards -->
      <meta name="twitter:card" content="summary_large_image">
      <meta name="twitter:title" content="Twitter Test Title">
      <meta name="twitter:description" content="Twitter Test Description">
      
      <!-- JSON-LD -->
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "SEO Agent Corp",
        "url": "https://example.com"
      }
      </script>
    </head>
    <body>
      <h1>Main Heading 1</h1>
      <h2>Sub Heading 2</h2>
      <h3>Sub Heading 3</h3>
      
      <p>Check out our <a href="/internal-link" rel="nofollow" target="_blank">Internal Link</a></p>
      <p>Visit <a href="https://external.com/page">External Site</a></p>
      
      <img src="/images/banner.jpg" alt="Test Banner" width="800" height="600" loading="lazy">
      <img src="https://external.com/avatar.png" alt="Avatar">
    </body>
    </html>
  `;

  const tokenUser = 'Bearer token_user_1';

  // --- 1. DIRECT SERVICE TESTS FOR HTML PARSER ---
  await test('parseHtml - Extract Title, Meta Description, Canonical, Robots, Lang, Charset', async () => {
    const result = parseHtml(sampleHtml, 'https://example.com/subpath/');

    assert.strictEqual(result.title, 'SEO Agent Test Page');
    assert.strictEqual(result.metaDescription, 'This is an automated test page for SEO auditing.');
    assert.strictEqual(result.metaRobots, 'index, follow');
    assert.strictEqual(result.language, 'en-US');
    assert.strictEqual(result.charset, 'UTF-8');
    assert.strictEqual(result.canonical, 'https://example.com/canonical-page');
  });

  await test('parseHtml - Extract Headings H1-H6 in order', async () => {
    const result = parseHtml(sampleHtml);

    assert.strictEqual(result.headings.length, 3);
    assert.strictEqual(result.headings[0].level, 'h1');
    assert.strictEqual(result.headings[0].text, 'Main Heading 1');
    assert.strictEqual(result.headings[1].level, 'h2');
    assert.strictEqual(result.headings[1].text, 'Sub Heading 2');
    assert.strictEqual(result.headings[2].level, 'h3');
    assert.strictEqual(result.headings[2].text, 'Sub Heading 3');
  });

  await test('parseHtml - Extract Images with src, alt, width, height, loading', async () => {
    const result = parseHtml(sampleHtml, 'https://example.com/base/');

    assert.strictEqual(result.images.length, 2);
    assert.strictEqual(result.images[0].src, 'https://example.com/images/banner.jpg');
    assert.strictEqual(result.images[0].alt, 'Test Banner');
    assert.strictEqual(result.images[0].width, '800');
    assert.strictEqual(result.images[0].height, '600');
    assert.strictEqual(result.images[0].loading, 'lazy');

    assert.strictEqual(result.images[1].src, 'https://external.com/avatar.png');
    assert.strictEqual(result.images[1].alt, 'Avatar');
  });

  await test('parseHtml - Extract Links with internal/external classification', async () => {
    const result = parseHtml(sampleHtml, 'https://example.com/base/');

    assert.strictEqual(result.links.length, 2);
    assert.strictEqual(result.links[0].href, 'https://example.com/internal-link');
    assert.strictEqual(result.links[0].text, 'Internal Link');
    assert.strictEqual(result.links[0].rel, 'nofollow');
    assert.strictEqual(result.links[0].target, '_blank');
    assert.strictEqual(result.links[0].isInternal, true);

    assert.strictEqual(result.links[1].href, 'https://external.com/page');
    assert.strictEqual(result.links[1].text, 'External Site');
    assert.strictEqual(result.links[1].isInternal, false);
  });

  await test('parseHtml - Extract Open Graph tags', async () => {
    const result = parseHtml(sampleHtml);

    assert.strictEqual(result.openGraph['og:title'], 'OG Test Title');
    assert.strictEqual(result.openGraph['og:description'], 'OG Test Description');
    assert.strictEqual(result.openGraph['og:image'], 'https://example.com/og-image.png');
  });

  await test('parseHtml - Extract Twitter Cards tags', async () => {
    const result = parseHtml(sampleHtml);

    assert.strictEqual(result.twitterCards['twitter:card'], 'summary_large_image');
    assert.strictEqual(result.twitterCards['twitter:title'], 'Twitter Test Title');
    assert.strictEqual(result.twitterCards['twitter:description'], 'Twitter Test Description');
  });

  await test('parseHtml - Extract JSON-LD structured data', async () => {
    const result = parseHtml(sampleHtml);

    assert.strictEqual(result.jsonLd.length, 1);
    assert.strictEqual(result.jsonLd[0]['@type'], 'Organization');
    assert.strictEqual(result.jsonLd[0].name, 'SEO Agent Corp');
  });

  // --- 2. API ENDPOINT TESTS FOR /api/v1/parse-html ---
  await test('POST /api/v1/parse-html - Reject unauthenticated requests', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-html`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: '<html></html>' })
    });
    assert.strictEqual(res.status, 401);
  });

  await test('POST /api/v1/parse-html - Return parsed SEO data object', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-html`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ html: sampleHtml, url: 'https://example.com' })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();

    assert.strictEqual(data.title, 'SEO Agent Test Page');
    assert.strictEqual(data.metaDescription, 'This is an automated test page for SEO auditing.');
    assert.strictEqual(data.headings.length, 3);
    assert.strictEqual(data.images.length, 2);
    assert.strictEqual(data.links.length, 2);
    assert.strictEqual(data.openGraph['og:title'], 'OG Test Title');
    assert.strictEqual(data.twitterCards['twitter:card'], 'summary_large_image');
    assert.strictEqual(data.jsonLd[0].name, 'SEO Agent Corp');
  });

  await test('POST /api/v1/parse-html - Reject missing HTML string with 400', async () => {
    const res = await fetch(`${baseUrl}/api/v1/parse-html`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    });
    assert.strictEqual(res.status, 400);
  });

  console.log(`\n🎉 HTML Parsing Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
