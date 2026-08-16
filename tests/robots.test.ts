import { RobotsParser, parseRobotsTxt } from '../src/services/robotsParser';
import assert from 'assert';

async function runTests() {
  console.log('🤖 Starting Robots.txt Parsing & Policy Test Suite...\n');
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

  test('1. Parse standard User-agent: * and Disallow rules', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /admin/
      Disallow: /private/
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/admin/dashboard', '*'), false);
    assert.strictEqual(parser.isAllowed('/private/secret.html', '*'), false);
    assert.strictEqual(parser.isAllowed('/public/about', '*'), true);
  });

  test('2. Specific User-agent rules take precedence over *', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /private/

      User-agent: Googlebot
      Disallow: /no-google/
      Allow: /private/
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/private/page', '*'), false);
    assert.strictEqual(parser.isAllowed('/private/page', 'Googlebot'), true);
    assert.strictEqual(parser.isAllowed('/no-google/page', 'Googlebot'), false);
  });

  test('3. Longer Allow directive overrides shorter Disallow directive', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /catalog/
      Allow: /catalog/public/
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/catalog/private-item', '*'), false);
    assert.strictEqual(parser.isAllowed('/catalog/public/item-123', '*'), true);
  });

  test('4. Wildcard * matching in path patterns', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /*.pdf$
      Disallow: /search*
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/document.pdf', '*'), false);
    assert.strictEqual(parser.isAllowed('/document.html', '*'), true);
    assert.strictEqual(parser.isAllowed('/search?q=seo', '*'), false);
  });

  test('5. End-of-path $ pattern matching', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /exact-end$
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/exact-end', '*'), false);
    assert.strictEqual(parser.isAllowed('/exact-end/more', '*'), true);
  });

  test('6. Ignore inline and block comments (#)', () => {
    const robotsTxt = `
      # Global configuration block
      User-agent: * # Applies to all crawlers
      Disallow: /temp/ # Temporary folder
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/temp/file', '*'), false);
    assert.strictEqual(parser.isAllowed('/permanent/file', '*'), true);
  });

  test('7. Parse Crawl-delay directives for default and custom user agents', () => {
    const robotsTxt = `
      User-agent: *
      Crawl-delay: 5

      User-agent: Bingbot
      Crawl-delay: 10
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.getCrawlDelay('*'), 5);
    assert.strictEqual(parser.getCrawlDelay('Bingbot'), 10);
  });

  test('8. Extract Sitemap URL directives', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /admin/

      Sitemap: https://example.com/sitemap.xml
      Sitemap: https://example.com/sitemap-news.xml
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.sitemaps.length, 2);
    assert.strictEqual(parser.sitemaps[0], 'https://example.com/sitemap.xml');
    assert.strictEqual(parser.sitemaps[1], 'https://example.com/sitemap-news.xml');
  });

  test('9. Grouped consecutive User-agent headers', () => {
    const robotsTxt = `
      User-agent: Googlebot
      User-agent: Bingbot
      Disallow: /shared-private/
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/shared-private/doc', 'Googlebot'), false);
    assert.strictEqual(parser.isAllowed('/shared-private/doc', 'Bingbot'), false);
    assert.strictEqual(parser.isAllowed('/shared-private/doc', 'OtherBot'), true);
  });

  test('10. Querying non-matching user-agent falls back to User-agent: *', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /global-restricted/

      User-agent: SpecialBot
      Disallow: /special-restricted/
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/global-restricted/', 'RandomAgent'), false);
    assert.strictEqual(parser.isAllowed('/special-restricted/', 'RandomAgent'), true);
  });

  test('11. Path matching subpath hierarchy vs root', () => {
    const robotsTxt = `
      User-agent: *
      Disallow: /
      Allow: /public/
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/', '*'), false);
    assert.strictEqual(parser.isAllowed('/index.html', '*'), false);
    assert.strictEqual(parser.isAllowed('/public/index.html', '*'), true);
  });

  test('12. Empty Disallow: directive allows all paths', () => {
    const robotsTxt = `
      User-agent: *
      Disallow:
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/anything', '*'), true);
  });

  test('13. toResult() outputs structured data object', () => {
    const robotsTxt = `
      Sitemap: https://example.com/sitemap.xml
      User-agent: *
      Disallow: /admin/
      Allow: /admin/login
      Crawl-delay: 2
    `;
    const parser = new RobotsParser(robotsTxt);
    const result = parser.toResult('*');

    assert.strictEqual(result.sitemaps[0], 'https://example.com/sitemap.xml');
    assert.strictEqual(result.crawlDelay, 2);
    assert.deepStrictEqual(result.allow, ['/admin/login']);
    assert.deepStrictEqual(result.disallow, ['/admin/']);
  });

  test('14. Case-insensitivity of directive names and user agent strings', () => {
    const robotsTxt = `
      USER-AGENT: GOOGLEBOT
      DISALLOW: /lowercase/
      ALLOW: /lowercase/public
    `;
    const parser = new RobotsParser(robotsTxt);
    assert.strictEqual(parser.isAllowed('/lowercase/private', 'googlebot'), false);
    assert.strictEqual(parser.isAllowed('/lowercase/public', 'Googlebot'), true);
  });

  test('15. parseRobotsTxt top-level utility function', () => {
    const robotsTxt = `
      Sitemap: https://test.org/sitemap.xml
      User-agent: *
      Disallow: /secret
    `;
    const res = parseRobotsTxt(robotsTxt, '*');
    assert.strictEqual(res.sitemaps[0], 'https://test.org/sitemap.xml');
    assert.deepStrictEqual(res.disallow, ['/secret']);
  });

  console.log(`\n🎉 Robots.txt Test Suite Completed: ${passedCount} passed, ${failedCount} failed.`);

  if (failedCount > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runTests();
