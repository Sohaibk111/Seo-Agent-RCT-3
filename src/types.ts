export interface Website {
  id: number;
  url: string;
  domain: string;
  company_name?: string;
  created_at: string;
}

export interface AuditResult {
  id: number;
  website_id: number;
  score: number;
  title?: string;
  title_length?: number;
  meta_description?: string;
  meta_description_length?: number;
  h1_tags: string[];
  canonical_url?: string;
  viewport?: string;
  images_count: number;
  images_without_alt: number;
  has_structured_data: boolean;
  has_sitemap: boolean;
  has_robots_txt: boolean;
  broken_links_count: number;
  created_at: string;
}

export interface KeywordResult {
  kw: string;
  intent: 'Informational' | 'Navigational' | 'Commercial' | 'Transactional';
  volume: number;
  kd: number; // 0-100 difficulty
  cpc: number;
  cluster: string;
}

export interface DomainMetrics {
  domain: string;
  provider: string;
  domain_age_days: number;
  registrar: string;
  domain_authority: number;
  backlinks_estimate: number;
  organic_traffic_monthly: number;
  extra: {
    dns_sec: boolean;
    ssl_valid: boolean;
    server_country: string;
  };
}

export interface RankResult {
  keyword: string;
  domain: string;
  position: number;
  checked_results: number;
  source: string;
}

export interface AIRecommendation {
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  detail: string;
}

export interface AIAnalysis {
  provider: string;
  summary: string;
  recommendations: AIRecommendation[];
}

export interface Lead {
  id: number;
  website_id: number;
  email: string;
  phone?: string;
  source: string;
}
