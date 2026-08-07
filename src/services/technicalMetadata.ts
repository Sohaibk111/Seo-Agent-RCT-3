import * as cheerio from 'cheerio';
import { FetchResult } from './httpFetcher';

export interface CacheHeaders {
  cacheControl?: string;
  expires?: string;
  etag?: string;
  lastModified?: string;
  pragma?: string;
  age?: string;
  vary?: string;
}

export interface TechnicalMetadata {
  id: string;
  url: string;
  responseTime: number; // in ms
  contentLength: number; // in bytes
  htmlSize: number; // in bytes
  wordCount: number;
  language: string;
  encoding: string;
  contentType: string;
  compression: string;
  cacheHeaders: CacheHeaders;
  rawHeaders: Record<string, string>;
  createdAt: string;
}

export class TechnicalMetadataManager {
  private static store: Map<string, TechnicalMetadata> = new Map();

  public static extractMetadata(
    url: string,
    html: string,
    headers: Record<string, string> = {},
    responseTime: number = 0
  ): TechnicalMetadata {
    const $ = cheerio.load(html || '');

    // 1. HTML size in bytes
    const htmlSize = Buffer.byteLength(html || '', 'utf-8');

    // 2. Content Length
    let contentLength = htmlSize;
    if (headers['content-length']) {
      const parsed = parseInt(headers['content-length'], 10);
      if (!isNaN(parsed) && parsed > 0) {
        contentLength = parsed;
      }
    }

    // 3. Word Count (Extract text from body, clean scripts/styles)
    $('script, style, noscript, svg, iframe').remove();
    const bodyText = $('body').text() || $.text() || '';
    const words = bodyText.trim().split(/\s+/).filter(w => w.length > 0);
    const wordCount = words.length;

    // 4. Language
    let language = $('html').attr('lang')?.trim() || '';
    if (!language && headers['content-language']) {
      language = headers['content-language'].trim();
    }
    if (!language) {
      language = 'unknown';
    }

    // 5. Encoding / Charset
    let encoding = $('meta[charset]').attr('charset')?.trim() || '';
    if (!encoding) {
      const httpEquiv = $('meta[http-equiv="Content-Type" i]').attr('content') || '';
      const match = httpEquiv.match(/charset=([^\s;]+)/i);
      if (match) {
        encoding = match[1];
      }
    }
    if (!encoding && headers['content-type']) {
      const match = headers['content-type'].match(/charset=([^\s;]+)/i);
      if (match) {
        encoding = match[1];
      }
    }
    if (!encoding) {
      encoding = 'utf-8';
    }

    // 6. Content-Type
    const contentType = headers['content-type'] || 'text/html';

    // 7. Compression
    const compression = headers['content-encoding'] || 'none';

    // 8. Cache Headers
    const cacheHeaders: CacheHeaders = {
      cacheControl: headers['cache-control'],
      expires: headers['expires'],
      etag: headers['etag'],
      lastModified: headers['last-modified'],
      pragma: headers['pragma'],
      age: headers['age'],
      vary: headers['vary']
    };

    const id = `tech_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const metadata: TechnicalMetadata = {
      id,
      url,
      responseTime,
      contentLength,
      htmlSize,
      wordCount,
      language,
      encoding,
      contentType,
      compression,
      cacheHeaders,
      rawHeaders: headers,
      createdAt: new Date().toISOString()
    };

    return metadata;
  }

  public static storeMetadata(metadata: TechnicalMetadata): TechnicalMetadata {
    this.store.set(metadata.id, metadata);
    return metadata;
  }

  public static getMetadata(id: string): TechnicalMetadata | undefined {
    return this.store.get(id);
  }

  public static listMetadata(): TechnicalMetadata[] {
    return Array.from(this.store.values());
  }

  public static clearStore(): void {
    this.store.clear();
  }
}
