import * as cheerio from 'cheerio';

export interface ImageDetail {
  src: string;
  alt: string;
  width?: string;
  height?: string;
  loading?: string;
}

export interface LinkDetail {
  href: string;
  text: string;
  rel?: string;
  target?: string;
  isInternal: boolean;
}

export interface HeadingDetail {
  level: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  text: string;
}

export interface ParsedSEOData {
  title: string;
  metaDescription: string;
  canonical: string;
  metaRobots: string;
  language: string;
  charset: string;
  headings: HeadingDetail[];
  images: ImageDetail[];
  links: LinkDetail[];
  openGraph: Record<string, string>;
  twitterCards: Record<string, string>;
  jsonLd: any[];
}

/**
 * Parses HTML content using Cheerio and extracts key SEO elements.
 */
export function parseHtml(html: string, baseUrl?: string): ParsedSEOData {
  const $ = cheerio.load(html || '');

  // 1. Title
  const title = $('title').first().text().trim();

  // 2. Meta description
  const metaDescription =
    $('meta[name="description" i]').attr('content')?.trim() ||
    $('meta[property="og:description" i]').attr('content')?.trim() ||
    '';

  // 3. Canonical
  let canonical = $('link[rel="canonical" i]').attr('href')?.trim() || '';
  if (canonical && baseUrl) {
    try {
      canonical = new URL(canonical, baseUrl).href;
    } catch {
      // Keep original canonical if URL parsing fails
    }
  }

  // 4. Meta Robots
  const metaRobots =
    $('meta[name="robots" i]').attr('content')?.trim() ||
    $('meta[name="googlebot" i]').attr('content')?.trim() ||
    '';

  // 5. Language
  const language = $('html').attr('lang')?.trim() || '';

  // 6. Charset
  let charset = $('meta[charset]').attr('charset')?.trim() || '';
  if (!charset) {
    const contentType = $('meta[http-equiv="Content-Type" i]').attr('content') || '';
    const match = contentType.match(/charset=([^\s;]+)/i);
    if (match) {
      charset = match[1];
    }
  }

  // 7. Headings H1-H6
  const headings: HeadingDetail[] = [];
  $('h1, h2, h3, h4, h5, h6').each((_, el) => {
    const tagName = el.tagName.toLowerCase() as HeadingDetail['level'];
    const text = $(el).text().replace(/\s+/g, ' ').trim();
    if (text) {
      headings.push({ level: tagName, text });
    }
  });

  // 8. Images
  const images: ImageDetail[] = [];
  $('img').each((_, el) => {
    let src = $(el).attr('src')?.trim() || '';
    if (src && baseUrl) {
      try {
        src = new URL(src, baseUrl).href;
      } catch {
        // Keep raw src
      }
    }
    const alt = $(el).attr('alt')?.trim() || '';
    const width = $(el).attr('width')?.trim();
    const height = $(el).attr('height')?.trim();
    const loading = $(el).attr('loading')?.trim();
    images.push({ src, alt, width, height, loading });
  });

  // 9. Links
  const links: LinkDetail[] = [];
  let baseOrigin = '';
  if (baseUrl) {
    try {
      baseOrigin = new URL(baseUrl).origin;
    } catch {
      baseOrigin = '';
    }
  }

  $('a[href]').each((_, el) => {
    let href = $(el).attr('href')?.trim() || '';
    let isInternal = false;

    if (href && baseUrl) {
      try {
        const resolved = new URL(href, baseUrl);
        isInternal = baseOrigin ? resolved.origin === baseOrigin : false;
        href = resolved.href;
      } catch {
        isInternal = false;
      }
    } else if (href.startsWith('/') || href.startsWith('#') || href.startsWith('.')) {
      isInternal = true;
    }

    const text = $(el).text().replace(/\s+/g, ' ').trim();
    const rel = $(el).attr('rel')?.trim();
    const target = $(el).attr('target')?.trim();

    links.push({ href, text, rel, target, isInternal });
  });

  // 10. Open Graph
  const openGraph: Record<string, string> = {};
  $('meta[property^="og:" i]').each((_, el) => {
    const property = $(el).attr('property')?.toLowerCase() || '';
    const content = $(el).attr('content')?.trim() || '';
    if (property && content) {
      openGraph[property] = content;
    }
  });

  // 11. Twitter Cards
  const twitterCards: Record<string, string> = {};
  $('meta[name^="twitter:" i], meta[property^="twitter:" i]').each((_, el) => {
    const key = ($(el).attr('name') || $(el).attr('property') || '').toLowerCase();
    const content = $(el).attr('content')?.trim() || '';
    if (key && content) {
      twitterCards[key] = content;
    }
  });

  // 12. JSON-LD
  const jsonLd: any[] = [];
  $('script[type="application/ld+json" i]').each((_, el) => {
    const rawContent = $(el).html()?.trim();
    if (rawContent) {
      try {
        const parsed = JSON.parse(rawContent);
        jsonLd.push(parsed);
      } catch {
        jsonLd.push({ raw: rawContent, parseError: true });
      }
    }
  });

  return {
    title,
    metaDescription,
    canonical,
    metaRobots,
    language,
    charset,
    headings,
    images,
    links,
    openGraph,
    twitterCards,
    jsonLd
  };
}
