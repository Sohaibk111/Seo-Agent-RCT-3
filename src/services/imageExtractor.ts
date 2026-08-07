import * as cheerio from 'cheerio';
import { fetchUrl } from './httpFetcher';

export interface ExtractedImage {
  src: string;
  alt: string;
  width?: string;
  height?: string;
  loading?: 'lazy' | 'eager' | string;
  dataSrc?: string;
  srcset?: string;
  fileSize?: number; // Size in bytes if available
  mimeType?: string;
  isMissingAlt: boolean;
  isMissingDimensions: boolean;
  isLazy: boolean;
}

export interface ImageExtractionResult {
  totalImages: number;
  missingAltCount: number;
  missingDimensionsCount: number;
  lazyLoadedCount: number;
  images: ExtractedImage[];
}

export function extractImagesFromHtml(html: string, baseUrl?: string): ImageExtractionResult {
  const $ = cheerio.load(html || '');
  const images: ExtractedImage[] = [];

  let missingAltCount = 0;
  let missingDimensionsCount = 0;
  let lazyLoadedCount = 0;

  $('img').each((_, el) => {
    let src = $(el).attr('src')?.trim() || $(el).attr('data-src')?.trim() || '';
    const dataSrc = $(el).attr('data-src')?.trim();
    const srcset = $(el).attr('srcset')?.trim();

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
    const loading = $(el).attr('loading')?.trim().toLowerCase();

    const isMissingAlt = alt.length === 0;
    const isMissingDimensions = !width || !height;
    const isLazy = loading === 'lazy' || !!dataSrc || $(el).hasClass('lazyload') || $(el).hasClass('lazy');

    if (isMissingAlt) missingAltCount++;
    if (isMissingDimensions) missingDimensionsCount++;
    if (isLazy) lazyLoadedCount++;

    images.push({
      src,
      alt,
      width,
      height,
      loading,
      dataSrc,
      srcset,
      isMissingAlt,
      isMissingDimensions,
      isLazy
    });
  });

  return {
    totalImages: images.length,
    missingAltCount,
    missingDimensionsCount,
    lazyLoadedCount,
    images
  };
}

/**
 * Optionally checks HEAD/GET headers for image URLs to retrieve file sizes in bytes.
 */
export async function enrichImageFileSizes(images: ExtractedImage[], timeoutMs: number = 5000): Promise<ExtractedImage[]> {
  const enriched = [...images];

  await Promise.all(
    enriched.map(async (img) => {
      if (!img.src || !img.src.startsWith('http')) return;
      try {
        const fetchRes = await fetchUrl(img.src, timeoutMs);
        if (fetchRes.status_code === 200) {
          const contentLength = fetchRes.headers['content-length'];
          if (contentLength) {
            const parsedSize = parseInt(contentLength, 10);
            if (!isNaN(parsedSize)) {
              img.fileSize = parsedSize;
            }
          }
          const contentType = fetchRes.headers['content-type'] || fetchRes.content_type;
          if (contentType) {
            img.mimeType = contentType;
          }
        }
      } catch {
        // Ignore network errors during header size enrichment
      }
    })
  );

  return enriched;
}
