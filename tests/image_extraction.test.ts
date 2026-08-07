import { app } from '../server';
import { extractImagesFromHtml } from '../src/services/imageExtractor';
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
  console.log('🖼️ Starting Image Metadata Extraction Test Suite...\n');
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

  const sampleHtml = `
    <html>
      <body>
        <img src="/images/hero.jpg" alt="Hero Banner" width="1200" height="600" loading="eager" />
        <img src="https://cdn.example.com/product.png" alt="Product Image" width="400" height="400" loading="lazy" />
        <img src="/images/no-alt.jpg" width="300" height="200" />
        <img src="/images/no-dimensions.png" alt="No Dim" loading="lazy" />
        <img data-src="/images/lazy-data.webp" alt="Lazy Data Src" class="lazyload" />
      </body>
    </html>
  `;

  // --- 1. UNIT TESTS ---

  await test('extractImagesFromHtml - Correctly extract src, alt, width, height, loading, and lazy status', async () => {
    const result = extractImagesFromHtml(sampleHtml, 'https://example.com');

    assert.strictEqual(result.totalImages, 5);
    assert.strictEqual(result.missingAltCount, 1);
    assert.strictEqual(result.missingDimensionsCount, 2);
    assert.strictEqual(result.lazyLoadedCount, 3); // product.png (lazy), no-dimensions.png (lazy), lazy-data.webp (data-src + lazyload class)

    // Hero image
    const hero = result.images[0];
    assert.strictEqual(hero.src, 'https://example.com/images/hero.jpg');
    assert.strictEqual(hero.alt, 'Hero Banner');
    assert.strictEqual(hero.width, '1200');
    assert.strictEqual(hero.height, '600');
    assert.strictEqual(hero.loading, 'eager');
    assert.strictEqual(hero.isMissingAlt, false);
    assert.strictEqual(hero.isMissingDimensions, false);
    assert.strictEqual(hero.isLazy, false);

    // Product image
    const product = result.images[1];
    assert.strictEqual(product.src, 'https://cdn.example.com/product.png');
    assert.strictEqual(product.loading, 'lazy');
    assert.strictEqual(product.isLazy, true);

    // Missing alt image
    const noAlt = result.images[2];
    assert.strictEqual(noAlt.isMissingAlt, true);
    assert.strictEqual(noAlt.alt, '');

    // Missing dimensions image
    const noDim = result.images[3];
    assert.strictEqual(noDim.isMissingDimensions, true);
    assert.strictEqual(noDim.width, undefined);

    // Lazy data-src image
    const lazyData = result.images[4];
    assert.strictEqual(lazyData.src, 'https://example.com/images/lazy-data.webp');
    assert.strictEqual(lazyData.dataSrc, '/images/lazy-data.webp');
    assert.strictEqual(lazyData.isLazy, true);
  });

  // --- 2. API ENDPOINT TESTS ---

  await test('POST /api/v1/extract-images - Extract image metadata via REST API', async () => {
    const res = await fetch(`${baseUrl}/api/v1/extract-images`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        html: sampleHtml,
        baseUrl: 'https://example.com'
      })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.totalImages, 5);
    assert.strictEqual(data.missingAltCount, 1);
    assert.strictEqual(data.images[0].src, 'https://example.com/images/hero.jpg');
  });

  console.log(`\n🎉 Image Extraction Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
