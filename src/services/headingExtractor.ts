import * as cheerio from 'cheerio';

export interface HeadingItem {
  id: string;
  tag: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  level: number; // 1 to 6
  text: string;
  elementId?: string;
  className?: string;
  isSkippedLevel: boolean; // True if this heading skips a level (e.g. H1 -> H3)
  parentTag?: string;
}

export interface HeadingTreeNode {
  heading: HeadingItem;
  children: HeadingTreeNode[];
}

export interface HeadingExtractionResult {
  totalHeadings: number;
  counts: {
    h1: number;
    h2: number;
    h3: number;
    h4: number;
    h5: number;
    h6: number;
  };
  issues: {
    missingH1: boolean;
    multipleH1: boolean;
    hasSkippedLevels: boolean;
    emptyHeadingsCount: number;
  };
  flatHeadings: HeadingItem[];
  tree: HeadingTreeNode[];
}

export function extractHeadingsFromHtml(html: string): HeadingExtractionResult {
  const $ = cheerio.load(html || '');
  const flatHeadings: HeadingItem[] = [];

  const counts = {
    h1: 0,
    h2: 0,
    h3: 0,
    h4: 0,
    h5: 0,
    h6: 0
  };

  let emptyHeadingsCount = 0;
  let hasSkippedLevels = false;
  let previousLevel = 0;

  $('h1, h2, h3, h4, h5, h6').each((_, el) => {
    const tagName = el.tagName.toLowerCase() as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
    const level = parseInt(tagName.replace('h', ''), 10);
    const text = $(el).text().trim();
    const elementId = $(el).attr('id')?.trim();
    const className = $(el).attr('class')?.trim();

    if (!text) {
      emptyHeadingsCount++;
    }

    counts[tagName]++;

    // Check level skipping (e.g. going from level 1 to level 3)
    let isSkippedLevel = false;
    if (previousLevel > 0 && level > previousLevel + 1) {
      isSkippedLevel = true;
      hasSkippedLevels = true;
    }

    flatHeadings.push({
      id: `h_${flatHeadings.length + 1}`,
      tag: tagName,
      level,
      text,
      elementId,
      className,
      isSkippedLevel
    });

    previousLevel = level;
  });

  // Build Hierarchical Tree
  const tree: HeadingTreeNode[] = [];
  const stack: { level: number; node: HeadingTreeNode }[] = [];

  for (const item of flatHeadings) {
    const node: HeadingTreeNode = { heading: item, children: [] };

    while (stack.length > 0 && stack[stack.length - 1].level >= item.level) {
      stack.pop();
    }

    if (stack.length === 0) {
      tree.push(node);
    } else {
      const parent = stack[stack.length - 1].node;
      parent.children.push(node);
      item.parentTag = parent.heading.tag;
    }

    stack.push({ level: item.level, node });
  }

  return {
    totalHeadings: flatHeadings.length,
    counts,
    issues: {
      missingH1: counts.h1 === 0,
      multipleH1: counts.h1 > 1,
      hasSkippedLevels,
      emptyHeadingsCount
    },
    flatHeadings,
    tree
  };
}
