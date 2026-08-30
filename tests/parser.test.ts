import { parseHtml } from '../src/services/htmlParser';
import { extractHeadingsFromHtml } from '../src/services/headingExtractor';
import { extractImagesFromHtml } from '../src/services/imageExtractor';
import assert from 'assert';

process.env.NODE_ENV = 'test';

async function runTests() {
  console.log('🏷️ Starting HTML Parser & Extraction Test Suite...\n');
  let passedCount = 0;
  let failedCount = 0;

  function test(name: string, fn: () => void) {
    try {
      fn();
      console.log(`  ✓ PASSED: ${name}`);
      passedCount++;
    } catch (err: any) {
      console.error(`  ✗ FAILED: ${name}`);
      console.error(`    Error: ${err.message}`);
      if (err.stack) console.error(err.stack);
      failedCount++;
    }
  }

  // --- TESTS ---

  test('1. Extract document title tag content', () => {
    const html = `<!DOCTYPE html><html><head><title>  SEO Audit &amp; Technical Analyzer  </title></head></html>`;
    const data = parseHtml(html);
    assert.strictEqual(data.title, 'SEO Audit & Technical Analyzer');
  });

  test('2. Extract meta description and fallback to og:description', () => {
    const htmlWithDesc = `<html><head><meta name="description" content="Primary meta description" /></head></html>`;
    const data1 = parseHtml(htmlWithDesc);
    assert.strictEqual(data1.metaDescription, 'Primary meta description');

    const htmlWithOg = `<html><head><meta property="og:description" content="Fallback OG description" /></head></html>`;
    const data2 = parseHtml(htmlWithOg);
    assert.strictEqual(data2.metaDescription, 'Fallback OG description');
  });

  test('3. Extract canonical URL and resolve relative URLs against baseUrl', () => {
    const html = `<html><head><link rel="canonical" href="/products/seo-tool" /></head></html>`;
    const data = parseHtml(html, 'https://agency.com/a/b');
    assert.strictEqual(data.canonical, 'https://agency.com/products/seo-tool');
  });

  test('4. Extract meta robots and meta googlebot directives', () => {
    const html = `<html><head><meta name="robots" content="index, follow, max-snippet:-1" /></head></html>`;
    const data = parseHtml(html);
    assert.strictEqual(data.metaRobots, 'index, follow, max-snippet:-1');
  });

  test('5. Extract html lang attribute and meta charset', () => {
    const html = `<html lang="en-US"><head><meta charset="utf-8" /></head></html>`;
    const data = parseHtml(html);
    assert.strictEqual(data.language, 'en-US');
    assert.strictEqual(data.charset, 'utf-8');
  });

  test('6. Extract heading hierarchy H1-H6 with clean text', () => {
    const html = `
      <html>
        <body>
          <h1> Main   Title </h1>
          <h2>Section 1</h2>
          <h3> Sub  Section </h3>
        </body>
      </html>
    `;
    const data = parseHtml(html);
    assert.strictEqual(data.headings.length, 3);
    assert.strictEqual(data.headings[0].level, 'h1');
    assert.strictEqual(data.headings[0].text, 'Main Title');
    assert.strictEqual(data.headings[2].level, 'h3');
    assert.strictEqual(data.headings[2].text, 'Sub Section');
  });

  test('7. Detect heading structural issues (multiple H1s, skipped levels, empty headings)', () => {
    const html = `
      <html>
        <body>
          <h1>Heading 1</h1>
          <h1>Heading 2</h1>
          <h3>Skipped Level H3</h3>
          <h2></h2>
        </body>
      </html>
    `;
    const analysis = extractHeadingsFromHtml(html);
    assert.strictEqual(analysis.counts.h1, 2);
    assert.strictEqual(analysis.issues.multipleH1, true);
    assert.strictEqual(analysis.issues.hasSkippedLevels, true);
    assert.strictEqual(analysis.issues.emptyHeadingsCount, 1);
  });

  test('8. Build hierarchical heading tree structure', () => {
    const html = `
      <html>
        <body>
          <h1>Root H1</h1>
          <h2>Child H2-A</h2>
          <h3>Grandchild H3</h3>
          <h2>Child H2-B</h2>
        </body>
      </html>
    `;
    const analysis = extractHeadingsFromHtml(html);
    assert.strictEqual(analysis.tree.length, 1);
    assert.strictEqual(analysis.tree[0].heading.text, 'Root H1');
    assert.strictEqual(analysis.tree[0].children.length, 2);
    assert.strictEqual(analysis.tree[0].children[0].heading.text, 'Child H2-A');
    assert.strictEqual(analysis.tree[0].children[0].children[0].heading.text, 'Grandchild H3');
  });

  test('9. Extract img tags with src, alt, width, height, and loading attributes', () => {
    const html = `
      <html>
        <body>
          <img src="/logo.png" alt="Company Logo" width="200" height="50" loading="lazy" />
        </body>
      </html>
    `;
    const data = parseHtml(html, 'https://example.com');
    assert.strictEqual(data.images.length, 1);
    assert.strictEqual(data.images[0].src, 'https://example.com/logo.png');
    assert.strictEqual(data.images[0].alt, 'Company Logo');
    assert.strictEqual(data.images[0].width, '200');
    assert.strictEqual(data.images[0].height, '50');
    assert.strictEqual(data.images[0].loading, 'lazy');
  });

  test('10. Resolve relative image URLs against baseUrl', () => {
    const html = `<img src="../assets/banner.jpg" alt="Banner" />`;
    const data = parseHtml(html, 'https://site.org/pages/sub/index.html');
    assert.strictEqual(data.images[0].src, 'https://site.org/pages/assets/banner.jpg');
  });

  test('11. Identify missing image alt attributes using extractImagesFromHtml', () => {
    const html = `
      <html>
        <body>
          <img src="/img1.png" alt="Valid alt text" />
          <img src="/img2.png" />
          <img src="/img3.png" alt="  " />
        </body>
      </html>
    `;
    const analysis = extractImagesFromHtml(html, 'https://test.com');
    assert.strictEqual(analysis.totalImages, 3);
    assert.strictEqual(analysis.missingAltCount, 2);
  });

  test('12. Extract links and classify as internal vs external', () => {
    const html = `
      <html>
        <body>
          <a href="/about">About Us</a>
          <a href="https://external.com/blog">External Blog</a>
        </body>
      </html>
    `;
    const data = parseHtml(html, 'https://mywebsite.com/home');
    assert.strictEqual(data.links.length, 2);
    assert.strictEqual(data.links[0].href, 'https://mywebsite.com/about');
    assert.strictEqual(data.links[0].isInternal, true);
    assert.strictEqual(data.links[1].href, 'https://external.com/blog');
    assert.strictEqual(data.links[1].isInternal, false);
  });

  test('13. Extract link rel and target attributes', () => {
    const html = `<a href="https://partner.com" rel="nofollow noopener" target="_blank">Partner</a>`;
    const data = parseHtml(html);
    assert.strictEqual(data.links[0].rel, 'nofollow noopener');
    assert.strictEqual(data.links[0].target, '_blank');
  });

  test('14. Extract Open Graph meta tags', () => {
    const html = `
      <html>
        <head>
          <meta property="og:title" content="OG Title Example" />
          <meta property="og:type" content="article" />
          <meta property="og:image" content="https://site.com/og.png" />
        </head>
      </html>
    `;
    const data = parseHtml(html);
    assert.strictEqual(data.openGraph['og:title'], 'OG Title Example');
    assert.strictEqual(data.openGraph['og:type'], 'article');
    assert.strictEqual(data.openGraph['og:image'], 'https://site.com/og.png');
  });

  test('15. Extract Twitter Card meta tags', () => {
    const html = `
      <html>
        <head>
          <meta name="twitter:card" content="summary_large_image" />
          <meta name="twitter:site" content="@seoagent" />
        </head>
      </html>
    `;
    const data = parseHtml(html);
    assert.strictEqual(data.twitterCards['twitter:card'], 'summary_large_image');
    assert.strictEqual(data.twitterCards['twitter:site'], '@seoagent');
  });

  test('16. Parse JSON-LD structured data and handle syntax errors gracefully', () => {
    const html = `
      <html>
        <head>
          <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "Organization",
              "name": "SEO Agent"
            }
          </script>
          <script type="application/ld+json">
            { invalid json }
          </script>
        </head>
      </html>
    `;
    const data = parseHtml(html);
    assert.strictEqual(data.jsonLd.length, 2);
    assert.strictEqual(data.jsonLd[0]['@type'], 'Organization');
    assert.strictEqual(data.jsonLd[1].parseError, true);
  });

  console.log(`\n🎉 Parser Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
