import { parseSitemapXml, discoverSitemapCandidateUrls } from '../src/services/sitemapParser';
import assert from 'assert';

async function runTests() {
  console.log('🗺️ Starting Sitemap XML Parsing & Discovery Test Suite...\n');
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

  test('1. Parse standard urlset XML and extract loc URLs', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
      <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
          <loc>https://example.com/</loc>
        </url>
        <url>
          <loc>https://example.com/about</loc>
        </url>
      </urlset>`;

    const res = parseSitemapXml(xml);
    assert.strictEqual(res.isIndex, false);
    assert.strictEqual(res.totalUrls, 2);
    assert.strictEqual(res.urls[0].loc, 'https://example.com/');
    assert.strictEqual(res.urls[1].loc, 'https://example.com/about');
  });

  test('2. Parse lastmod, changefreq, and priority numeric values', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
      <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
          <loc>https://example.com/pricing</loc>
          <lastmod>2026-08-01</lastmod>
          <changefreq>weekly</changefreq>
          <priority>0.8</priority>
        </url>
      </urlset>`;

    const res = parseSitemapXml(xml);
    assert.strictEqual(res.urls[0].loc, 'https://example.com/pricing');
    assert.strictEqual(res.urls[0].lastmod, '2026-08-01');
    assert.strictEqual(res.urls[0].changefreq, 'weekly');
    assert.strictEqual(res.urls[0].priority, 0.8);
  });

  test('3. Parse Image Sitemaps (image:image, image:loc, image:title, image:caption)', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
      <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
              xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
        <url>
          <loc>https://example.com/gallery</loc>
          <image:image>
            <image:loc>https://example.com/images/photo1.jpg</image:loc>
            <image:title>Beautiful Sunset</image:title>
            <image:caption>Sunset over the mountains</image:caption>
          </image:image>
        </url>
      </urlset>`;

    const res = parseSitemapXml(xml);
    assert.strictEqual(res.totalImages, 1);
    assert.strictEqual(res.urls[0].images.length, 1);
    assert.strictEqual(res.urls[0].images[0].loc, 'https://example.com/images/photo1.jpg');
    assert.strictEqual(res.urls[0].images[0].title, 'Beautiful Sunset');
    assert.strictEqual(res.urls[0].images[0].caption, 'Sunset over the mountains');
  });

  test('4. Accurate calculation of totalUrls and totalImages metrics', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
      <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
              xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
        <url>
          <loc>https://example.com/p1</loc>
          <image:image><image:loc>https://example.com/img1.jpg</image:loc></image:image>
          <image:image><image:loc>https://example.com/img2.jpg</image:loc></image:image>
        </url>
        <url>
          <loc>https://example.com/p2</loc>
        </url>
      </urlset>`;

    const res = parseSitemapXml(xml);
    assert.strictEqual(res.totalUrls, 2);
    assert.strictEqual(res.totalImages, 2);
  });

  test('5. Parse Sitemap Index (sitemapindex) files and extract child sitemaps', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
      <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap>
          <loc>https://example.com/sitemap-posts.xml</loc>
          <lastmod>2026-08-05</lastmod>
        </sitemap>
        <sitemap>
          <loc>https://example.com/sitemap-pages.xml</loc>
        </sitemap>
      </sitemapindex>`;

    const res = parseSitemapXml(xml);
    assert.strictEqual(res.isIndex, true);
    assert.strictEqual(res.childSitemaps.length, 2);
    assert.strictEqual(res.childSitemaps[0].loc, 'https://example.com/sitemap-posts.xml');
    assert.strictEqual(res.childSitemaps[0].lastmod, '2026-08-05');
    assert.strictEqual(res.childSitemaps[1].loc, 'https://example.com/sitemap-pages.xml');
  });

  test('6. Distinguish index sitemap from regular urlset', () => {
    const urlsetXml = `<urlset><url><loc>https://site.com/a</loc></url></urlset>`;
    const indexXml = `<sitemapindex><sitemap><loc>https://site.com/s1.xml</loc></sitemap></sitemapindex>`;

    const res1 = parseSitemapXml(urlsetXml);
    assert.strictEqual(res1.isIndex, false);

    const res2 = parseSitemapXml(indexXml);
    assert.strictEqual(res2.isIndex, true);
  });

  test('7. Handle XML with default or custom XML namespaces', () => {
    const nsXml = `<?xml version="1.0" encoding="UTF-8"?>
      <urlset xmlns:xhtml="http://www.w3.org/1999/xhtml">
        <url>
          <loc>https://example.com/es/inicio</loc>
        </url>
      </urlset>`;

    const res = parseSitemapXml(nsXml);
    assert.strictEqual(res.totalUrls, 1);
    assert.strictEqual(res.urls[0].loc, 'https://example.com/es/inicio');
  });

  test('8. discoverSitemapCandidateUrls generates standard sitemap locations', () => {
    const candidates = discoverSitemapCandidateUrls('https://mywebsite.org/blog/post-1');
    assert.ok(candidates.includes('https://mywebsite.org/sitemap.xml'));
    assert.ok(candidates.includes('https://mywebsite.org/sitemap_index.xml'));
  });

  test('9. discoverSitemapCandidateUrls merges robots.txt sitemap directives', () => {
    const robotsSitemaps = ['https://mywebsite.org/custom-sitemap.xml'];
    const candidates = discoverSitemapCandidateUrls('https://mywebsite.org/', robotsSitemaps);

    assert.strictEqual(candidates[0], 'https://mywebsite.org/custom-sitemap.xml');
    assert.ok(candidates.includes('https://mywebsite.org/sitemap.xml'));
  });

  test('10. discoverSitemapCandidateUrls deduplicates candidate URLs', () => {
    const robotsSitemaps = ['https://mywebsite.org/sitemap.xml'];
    const candidates = discoverSitemapCandidateUrls('https://mywebsite.org/', robotsSitemaps);

    const count = candidates.filter(c => c === 'https://mywebsite.org/sitemap.xml').length;
    assert.strictEqual(count, 1);
  });

  test('11. Gracefully handle empty or non-XML string input', () => {
    const resEmpty = parseSitemapXml('');
    assert.strictEqual(resEmpty.totalUrls, 0);

    const resGarbage = parseSitemapXml('<html><body>not a sitemap</body></html>');
    assert.strictEqual(resGarbage.totalUrls, 0);
  });

  test('12. Parse URL entries with missing optional metadata fields', () => {
    const xml = `<urlset><url><loc>https://example.com/minimal</loc></url></urlset>`;
    const res = parseSitemapXml(xml);

    assert.strictEqual(res.urls[0].loc, 'https://example.com/minimal');
    assert.strictEqual(res.urls[0].lastmod, undefined);
    assert.strictEqual(res.urls[0].changefreq, undefined);
    assert.strictEqual(res.urls[0].priority, undefined);
  });

  test('13. Parse invalid numeric priority without NaN error', () => {
    const xml = `<urlset><url><loc>https://example.com/bad-prio</loc><priority>high</priority></url></urlset>`;
    const res = parseSitemapXml(xml);

    assert.strictEqual(res.urls[0].priority, undefined);
  });

  test('14. Parse multiple image tags on a single URL entry', () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
      <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
          <loc>https://example.com/portfolio</loc>
          <image:image><image:loc>https://example.com/imgA.png</image:loc></image:image>
          <image:image><image:loc>https://example.com/imgB.png</image:loc></image:image>
          <image:image><image:loc>https://example.com/imgC.png</image:loc></image:image>
        </url>
      </urlset>`;

    const res = parseSitemapXml(xml);
    assert.strictEqual(res.urls[0].images.length, 3);
  });

  test('15. Normalize whitespace in loc tags', () => {
    const xml = `<urlset><url><loc>   https://example.com/spaced-url   </loc></url></urlset>`;
    const res = parseSitemapXml(xml);

    assert.strictEqual(res.urls[0].loc, 'https://example.com/spaced-url');
  });

  console.log(`\n🎉 Sitemap Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
