import { app } from '../server';
import { extractHeadingsFromHtml } from '../src/services/headingExtractor';
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
  console.log('🏷️ Starting Headings Extraction & Hierarchy Analysis Test Suite...\n');
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
        <h1 id="main-title" class="title">Main Title</h1>
        <h2 id="section-1">Section 1</h2>
        <h3>Subsection 1.1</h3>
        <h4>Sub-subsection 1.1.1</h4>
        <h5>Deep Heading Level 5</h5>
        <h6>Deepest Heading Level 6</h6>
        <h2>Section 2</h2>
        <h4>Skipped Level Heading (H2 -> H4)</h4>
        <h1>Second H1 Title</h1>
        <h2></h2>
      </body>
    </html>
  `;

  // --- 1. UNIT TESTS ---

  await test('extractHeadingsFromHtml - Extract H1 through H6 and count occurrences accurately', async () => {
    const result = extractHeadingsFromHtml(sampleHtml);

    assert.strictEqual(result.totalHeadings, 10);
    assert.strictEqual(result.counts.h1, 2);
    assert.strictEqual(result.counts.h2, 3);
    assert.strictEqual(result.counts.h3, 1);
    assert.strictEqual(result.counts.h4, 2);
    assert.strictEqual(result.counts.h5, 1);
    assert.strictEqual(result.counts.h6, 1);
  });

  await test('extractHeadingsFromHtml - Detect structural issues (multiple H1, skipped levels, empty heading)', async () => {
    const result = extractHeadingsFromHtml(sampleHtml);

    assert.strictEqual(result.issues.multipleH1, true);
    assert.strictEqual(result.issues.missingH1, false);
    assert.strictEqual(result.issues.hasSkippedLevels, true);
    assert.strictEqual(result.issues.emptyHeadingsCount, 1);
  });

  await test('extractHeadingsFromHtml - Build hierarchical tree structure correctly', async () => {
    const result = extractHeadingsFromHtml(sampleHtml);

    assert.ok(result.tree.length > 0);
    const rootH1 = result.tree[0];
    assert.strictEqual(rootH1.heading.tag, 'h1');
    assert.strictEqual(rootH1.heading.text, 'Main Title');
    assert.strictEqual(rootH1.heading.elementId, 'main-title');
    assert.strictEqual(rootH1.heading.className, 'title');

    // Section 1 should be child of root H1
    const section1Node = rootH1.children.find(c => c.heading.text === 'Section 1');
    assert.ok(section1Node);
    assert.strictEqual(section1Node!.heading.tag, 'h2');
    assert.strictEqual(section1Node!.heading.parentTag, 'h1');

    // Subsection 1.1 should be child of Section 1
    const subNode = section1Node!.children.find(c => c.heading.text === 'Subsection 1.1');
    assert.ok(subNode);
    assert.strictEqual(subNode!.heading.tag, 'h3');
    assert.strictEqual(subNode!.heading.parentTag, 'h2');
  });

  // --- 2. REST API ENDPOINT TESTS ---

  await test('POST /api/v1/extract-headings - Extract headings via REST API', async () => {
    const res = await fetch(`${baseUrl}/api/v1/extract-headings`, {
      method: 'POST',
      headers: {
        'Authorization': tokenUser,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        html: sampleHtml
      })
    });

    assert.strictEqual(res.status, 200);
    const data = await res.json();
    assert.strictEqual(data.totalHeadings, 10);
    assert.strictEqual(data.counts.h1, 2);
    assert.strictEqual(data.issues.multipleH1, true);
    assert.ok(Array.isArray(data.flatHeadings));
    assert.ok(Array.isArray(data.tree));
  });

  console.log(`\n🎉 Headings Extraction Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);
  await stopTestServer();

  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
