import { app } from '../server';
import { TechnicalMetadataManager } from '../src/services/technicalMetadata';
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
  console.log('⚡ Starting Technical Metadata Extraction Test Suite...\n');
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
    <!DOCTYPE html>
    <html lang="fr">
      <head>
        <meta charset="iso-8859-1" />
        <title>Technical Metadata Test Page</title>
      </head>
      <body>
        <h1>Bienvenue sur notre site SEO</h1>
        <p>This is a paragraph with several words to count accurately during technical metadata calculation.</p>
        <script>console.log("script ignored from word count");</script>
      </body>
    </html>
  `;

  const sampleHeaders = {
    'content-type': 'text/html; charset=iso-8859-1',
    'content-length': '1024',
    'content-encoding': 'gzip',
    'cache-control': 'public, max-age=3600',
    'etag': 'W/"123456789"',
    'expires': 'Wed, 21 Oct 2026 07:28:00 GMT',
    'last-modified': 'Tue, 15 Sep 2026 12:00:00 GMT',
    'vary': 'Accept-Encoding'
  };

  // --- 1. UNIT TESTS ---

  await test('TechnicalMetadataManager - Extract technical metrics accurately', async () => {
    const meta = TechnicalMetadataManager.extractMetadata(
      'https://example.fr/page',
      sampleHtml,
      sampleHeaders,
      145
    );

    assert.strictEqual(meta.url, 'https://example.fr/page');
    assert.strictEqual(meta.responseTime, 145);
    assert.strictEqual(meta.contentLength, 1024);
    assert.ok(meta.htmlSize > 0);
    assert.strictEqual(meta.language, 'fr');
    assert.strictEqual(meta.encoding, 'iso-8859-1');
    assert.strictEqual(meta.contentType, 'text/html; charset=iso-8859-1');
    assert.strictEqual(meta.compression, 'gzip');
    assert.strictEqual(meta.cacheHeaders.cacheControl, 'public, max-age=3600');
    assert.strictEqual(meta.cacheHeaders.etag, 'W/"123456789"');
    assert.ok(meta.wordCount >= 10);
  });

  // --- 2. REST API ENDPOINT TESTS ---

  let recordId = '';

  await test('POST /api/v1/technical-metadata/extract - Extract and store metadata via REST API', async () => {
    const res = await fetch(`${baseUrl}/api/v1/technical-metadata/extract`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: 'https://example.com/test-tech',
        html: sampleHtml,
        headers: sampleHeaders,
        responseTime: 210
      })
    });

    assert.strictEqual(res.status, 201);
    const data = await res.json();
    assert.ok(data.id);
    assert.strictEqual(data.url, 'https://example.com/test-tech');
    assert.strictEqual(data.responseTime, 210);
    assert.strictEqual(data.contentLength, 1024);
    assert.strictEqual(data.language, 'fr');
    assert.strictEqual(data.encoding, 'iso-8859-1');
    assert.strictEqual(data.compression, 'gzip');
    assert.strictEqual(data.cacheHeaders.cacheControl, 'public, max-age=3600');

    recordId = data.id;
  });

  await test('GET /api/v1/technical-metadata/:id - Retrieve stored record by ID', async () => {
    const res = await fetch(`${baseUrl}/api/v1/technical-metadata/${recordId}`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.id, recordId);
    assert.strictEqual(data.url, 'https://example.com/test-tech');
  });

  await test('GET /api/v1/technical-metadata - List all stored records', async () => {
    const res = await fetch(`${baseUrl}/api/v1/technical-metadata`, {
      headers: { 'Authorization': tokenUser }
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.ok(data.total >= 1);
    assert.ok(Array.isArray(data.records));
  });

  console.log(`\n🎉 Technical Metadata Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
