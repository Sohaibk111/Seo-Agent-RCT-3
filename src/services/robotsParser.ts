export interface AgentRule {
  userAgent: string;
  allow: string[];
  disallow: string[];
  crawlDelay?: number;
}

export interface ParsedRobotsData {
  sitemaps: string[];
  rules: Record<string, AgentRule>;
  crawlDelay?: number;
  allow: string[];
  disallow: string[];
}

export class RobotsParser {
  private rawContent: string;
  public sitemaps: string[] = [];
  public rules: Record<string, AgentRule> = {};

  constructor(content: string = '') {
    this.rawContent = content;
    if (content) {
      this.parse(content);
    }
  }

  public parse(content: string): void {
    this.rawContent = content;
    this.sitemaps = [];
    this.rules = {};

    let currentAgents: string[] = [];
    let expectingDirectives = false;
    const lines = content.split(/\r?\n/);

    for (const rawLine of lines) {
      // Strip comments
      const line = rawLine.split('#')[0].trim();
      if (!line || !line.includes(':')) continue;

      const colonIdx = line.indexOf(':');
      const key = line.slice(0, colonIdx).trim().toLowerCase();
      const value = line.slice(colonIdx + 1).trim();

      if (key === 'user-agent') {
        const agent = value.toLowerCase();
        if (expectingDirectives) {
          // New record block started
          currentAgents = [agent];
          expectingDirectives = false;
        } else {
          // Consecutive user-agent line for the same block
          if (!currentAgents.includes(agent)) {
            currentAgents.push(agent);
          }
        }

        for (const ag of currentAgents) {
          if (!this.rules[ag]) {
            this.rules[ag] = {
              userAgent: ag,
              allow: [],
              disallow: []
            };
          }
        }
      } else if (key === 'sitemap') {
        if (value && !this.sitemaps.includes(value)) {
          this.sitemaps.push(value);
        }
      } else if (currentAgents.length > 0) {
        expectingDirectives = true;
        for (const ag of currentAgents) {
          const rule = this.rules[ag];
          if (key === 'allow' && value) {
            rule.allow.push(value);
          } else if (key === 'disallow' && value) {
            rule.disallow.push(value);
          } else if (key === 'crawl-delay') {
            const delay = parseFloat(value);
            if (!isNaN(delay)) {
              rule.crawlDelay = delay;
            }
          }
        }
      }
    }
  }

  public getRuleForAgent(userAgent: string = '*'): AgentRule | undefined {
    const agLower = userAgent.toLowerCase();
    if (this.rules[agLower]) {
      return this.rules[agLower];
    }
    if (this.rules['*']) {
      return this.rules['*'];
    }
    return undefined;
  }

  public isAllowed(path: string, userAgent: string = '*'): boolean {
    const rule = this.getRuleForAgent(userAgent);
    if (!rule) return true;

    let longestMatchLen = -1;
    let allowed = true;

    for (const dis of rule.disallow) {
      if (this.pathMatches(path, dis)) {
        if (dis.length > longestMatchLen) {
          longestMatchLen = dis.length;
          allowed = false;
        }
      }
    }

    for (const al of rule.allow) {
      if (this.pathMatches(path, al)) {
        if (al.length >= longestMatchLen) {
          longestMatchLen = al.length;
          allowed = true;
        }
      }
    }

    return allowed;
  }

  public getCrawlDelay(userAgent: string = '*'): number | undefined {
    const rule = this.getRuleForAgent(userAgent);
    return rule?.crawlDelay;
  }

  private pathMatches(path: string, pattern: string): boolean {
    if (!pattern) return false;
    let regexStr = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\\\*/g, '.*');
    if (regexStr.endsWith('\\$')) {
      regexStr = regexStr.slice(0, -2) + '$';
    } else {
      regexStr = '^' + regexStr;
    }
    try {
      const reg = new RegExp(regexStr);
      return reg.test(path);
    } catch {
      return path.startsWith(pattern);
    }
  }

  public toResult(userAgent: string = '*'): ParsedRobotsData {
    const rule = this.getRuleForAgent(userAgent);
    return {
      sitemaps: this.sitemaps,
      rules: this.rules,
      crawlDelay: rule?.crawlDelay,
      allow: rule?.allow || [],
      disallow: rule?.disallow || []
    };
  }
}

export function parseRobotsTxt(content: string, userAgent: string = '*'): ParsedRobotsData {
  const parser = new RobotsParser(content);
  return parser.toResult(userAgent);
}
