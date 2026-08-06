import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import { createServer as createViteServer } from 'vite';
import path from 'path';

export const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

// --- DATA MODELS & ENTITIES ---

export interface UserRecord {
  id: number;
  email: string;
  username: string;
  role: string;
}

export interface WebsiteRecord {
  id: number;
  user_id: number;
  url: string;
  domain: string;
  company_name?: string;
  created_at: string;
}

export interface AuditRecord {
  id: number;
  website_id: number;
  user_id: number;
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

export interface LeadRecord {
  id: number;
  website_id: number;
  user_id: number;
  email: string;
  phone?: string;
  source: string;
}

export interface ReportRecord {
  id: number;
  website_id: number;
  user_id: number;
  title: string;
  format: string;
  created_at: string;
}

export interface JobRecord {
  id: number;
  user_id: number;
  website_id?: number;
  job_type: string;
  status: string;
  progress: number;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  updated_at: string;
  error_message?: string;
  result_reference?: any;
}

// --- DATA STORES ---

export const jobs: JobRecord[] = [];

export const users: UserRecord[] = [
  { id: 1, email: 'admin@seoagent.app', username: 'admin', role: 'admin' },
  { id: 2, email: 'userb@seoagent.app', username: 'userb', role: 'user' },
];

export const websites: WebsiteRecord[] = [
  { id: 1, user_id: 1, url: 'https://techflow-seo.com', domain: 'techflow-seo.com', company_name: 'TechFlow Inc.', created_at: new Date().toISOString() },
  { id: 2, user_id: 1, url: 'https://acme-analytics.io', domain: 'acme-analytics.io', company_name: 'Acme Analytics', created_at: new Date().toISOString() }
];

export const auditResults: AuditRecord[] = [
  {
    id: 101,
    website_id: 1,
    user_id: 1,
    score: 84,
    title: 'TechFlow - Next Gen AI SEO Automation & Keyword Intelligence Platform',
    title_length: 68,
    meta_description: 'Streamline your organic traffic growth with automated site audits, intent-driven keyword research, and SERP rank tracking.',
    meta_description_length: 135,
    h1_tags: ['Automate Your Technical SEO & Rank Higher Today'],
    canonical_url: 'https://techflow-seo.com',
    viewport: 'width=device-width, initial-scale=1.0',
    images_count: 14,
    images_without_alt: 2,
    has_structured_data: true,
    has_sitemap: true,
    has_robots_txt: true,
    broken_links_count: 0,
    created_at: new Date().toISOString()
  }
];

export const leads: LeadRecord[] = [
  { id: 1, website_id: 1, user_id: 1, email: 'contact@techflow-seo.com', phone: '+1 (555) 234-5678', source: 'footer_scrape' },
  { id: 2, website_id: 1, user_id: 1, email: 'growth@techflow-seo.com', source: 'meta_contacts' }
];

export const reports: ReportRecord[] = [
  { id: 1, website_id: 1, user_id: 1, title: 'Technical SEO Audit Report - TechFlow', format: 'pdf', created_at: new Date().toISOString() }
];

// --- AUTHENTICATION HELPERS & MIDDLEWARE ---

export function getUserByToken(authHeader?: string): UserRecord | null {
  if (!authHeader) return null;
  const token = authHeader.replace(/^Bearer\s+/i, '').trim();
  if (!token) return null;

  if (token === 'mock_jwt_token_sample' || token === 'token_user_1' || token === 'jwt_admin') {
    return users[0]; // User 1
  }
  if (token === 'token_user_2' || token === 'jwt_user_b') {
    return users[1]; // User 2
  }
  if (token.startsWith('token_user_')) {
    const id = parseInt(token.replace('token_user_', ''), 10);
    const found = users.find(u => u.id === id);
    if (found) return found;
  }
  return null;
}

export interface AuthenticatedRequest extends Request {
  user?: UserRecord;
}

export function requireAuth(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  const user = getUserByToken(req.headers.authorization);
  if (!user) {
    return res.status(401).json({ error: 'Unauthorized', detail: 'Authentication credentials were missing or invalid' });
  }
  req.user = user;
  next();
}

// --- REUSABLE AUTHORIZATION & OWNERSHIP HELPERS ---

export function checkWebsiteOwnership(websiteId: number, currentUserId: number): { website: WebsiteRecord | null; status: 200 | 403 | 404 } {
  const website = websites.find(w => w.id === websiteId);
  if (!website) {
    return { website: null, status: 404 };
  }
  if (website.user_id !== currentUserId) {
    return { website: null, status: 403 };
  }
  return { website, status: 200 };
}

export function checkAuditOwnership(auditId: number, currentUserId: number): { audit: AuditRecord | null; status: 200 | 403 | 404 } {
  const audit = auditResults.find(a => a.id === auditId);
  if (!audit) {
    return { audit: null, status: 404 };
  }
  if (audit.user_id !== currentUserId) {
    return { audit: null, status: 403 };
  }
  return { audit, status: 200 };
}

export function checkDomainOwnership(domain: string, currentUserId: number): { website: WebsiteRecord | null; status: 200 | 403 | 404 } {
  const cleanDomain = domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '').toLowerCase();
  const existing = websites.find(w => w.domain.toLowerCase() === cleanDomain);
  if (!existing) {
    return { website: null, status: 404 };
  }
  if (existing.user_id !== currentUserId) {
    return { website: null, status: 403 };
  }
  return { website: existing, status: 200 };
}

export function checkJobOwnership(jobId: number, currentUserId: number): { job: JobRecord | null; status: 200 | 403 | 404 } {
  const job = jobs.find(j => j.id === jobId);
  if (!job) {
    return { job: null, status: 404 };
  }
  if (job.user_id !== currentUserId) {
    return { job: null, status: 403 };
  }
  return { job, status: 200 };
}

// --- REST API ENDPOINTS ---

app.get('/api/v1/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// Authentication Routes
app.post('/api/v1/auth/register', (req: Request, res: Response) => {
  const { email, username } = req.body;
  if (!email) return res.status(400).json({ error: 'Email is required' });

  let existingUser = users.find(u => u.email === email);
  if (!existingUser) {
    existingUser = {
      id: users.length + 1,
      email,
      username: username || email.split('@')[0],
      role: 'user'
    };
    users.push(existingUser);
  }

  const token = `token_user_${existingUser.id}`;
  res.json({ id: existingUser.id, email: existingUser.email, access_token: token, token_type: 'bearer' });
});

app.post('/api/v1/auth/login', (req: Request, res: Response) => {
  const { email, username } = req.body;
  const user = users.find(u => (email && u.email === email) || (username && u.username === username)) || users[0];
  const token = `token_user_${user.id}`;
  res.json({ access_token: token, token_type: 'bearer', username: user.username, user_id: user.id });
});

app.get('/api/v1/auth/me', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  res.json(req.user);
});

// Websites Routes
app.get('/api/v1/websites', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const userWebsites = websites.filter(w => w.user_id === req.user!.id);
  res.json(userWebsites);
});

app.get('/api/v1/websites/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.id, 10);
  const { website, status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  res.json(website);
});

app.delete('/api/v1/websites/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const siteIndex = websites.findIndex(w => w.id === websiteId);
  if (siteIndex !== -1) websites.splice(siteIndex, 1);

  for (let i = auditResults.length - 1; i >= 0; i--) {
    if (auditResults[i].website_id === websiteId) auditResults.splice(i, 1);
  }
  for (let i = leads.length - 1; i >= 0; i--) {
    if (leads[i].website_id === websiteId) leads.splice(i, 1);
  }
  for (let i = reports.length - 1; i >= 0; i--) {
    if (reports[i].website_id === websiteId) reports.splice(i, 1);
  }

  res.json({ message: 'Website deleted successfully', id: websiteId });
});

// Technical Audit Routes
app.post('/api/v1/audit', requireAuth, async (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (!url && !website_id) {
    return res.status(400).json({ error: 'URL or website_id is required' });
  }

  try {
    let targetWebsite: WebsiteRecord;

    if (website_id) {
      const siteId = parseInt(website_id, 10);
      const { website, status } = checkWebsiteOwnership(siteId, req.user!.id);
      if (status === 404) return res.status(404).json({ error: 'Website not found' });
      if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
      targetWebsite = website!;
    } else {
      const targetUrl = url.startsWith('http') ? url : `https://${url}`;
      const domain = new URL(targetUrl).hostname;
      const domainCheck = checkDomainOwnership(domain, req.user!.id);
      if (domainCheck.status === 403) {
        return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
      }

      if (domainCheck.status === 200 && domainCheck.website) {
        targetWebsite = domainCheck.website;
      } else {
        targetWebsite = {
          id: websites.length + 1,
          user_id: req.user!.id,
          url: targetUrl,
          domain,
          company_name: domain.split('.')[0].toUpperCase(),
          created_at: new Date().toISOString()
        };
        websites.push(targetWebsite);
      }
    }

    const missingAlt = Math.floor(Math.random() * 3);
    const brokenLinks = Math.floor(Math.random() * 2);
    const auditScore = Math.min(100, Math.max(50, 95 - (missingAlt * 4) - (brokenLinks * 10)));

    const newAudit: AuditRecord = {
      id: auditResults.length + 101,
      website_id: targetWebsite.id,
      user_id: req.user!.id,
      score: auditScore,
      title: `${targetWebsite.company_name} - Official Website & Product Overview`,
      title_length: 58,
      meta_description: `Learn how ${targetWebsite.company_name} delivers industry-leading products with fast performance.`,
      meta_description_length: 145,
      h1_tags: [`Welcome to ${targetWebsite.company_name}`],
      canonical_url: targetWebsite.url,
      viewport: 'width=device-width, initial-scale=1.0',
      images_count: 12,
      images_without_alt: missingAlt,
      has_structured_data: true,
      has_sitemap: true,
      has_robots_txt: true,
      broken_links_count: brokenLinks,
      created_at: new Date().toISOString()
    };
    auditResults.push(newAudit);

    const newLead: LeadRecord = {
      id: leads.length + 1,
      website_id: targetWebsite.id,
      user_id: req.user!.id,
      email: `info@${targetWebsite.domain}`,
      source: 'domain_whois'
    };
    leads.push(newLead);

    res.json({
      website: targetWebsite,
      audit: newAudit,
      leads_found: 1
    });
  } catch (err: any) {
    res.status(500).json({ error: 'Failed to process website audit: ' + err.message });
  }
});

app.get('/api/v1/audit/:website_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.website_id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const results = auditResults.filter(a => a.website_id === websiteId && a.user_id === req.user!.id);
  res.json(results);
});

app.post('/api/v1/audit/site-level', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (website_id) {
    const { status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (url) {
    const domain = url.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }
  res.json({
    sitemap: { found: true, url: `${url}/sitemap.xml`, total_urls: 42 },
    robots_txt: { found: true, url: `${url}/robots.txt`, allow_all: true }
  });
});

// AI Analyze Recommendations
app.get('/api/v1/ai/analyze/:audit_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const auditId = parseInt(req.params.audit_id, 10);
  const { audit, status } = checkAuditOwnership(auditId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Audit result not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this audit' });

  res.json({
    provider: 'gemini-3.6-flash',
    summary: `Technical audit for Audit #${audit!.id} scores ${audit!.score}/100. Core title and canonical tags are healthy, but image alt text and broken links present immediate optimization targets.`,
    recommendations: [
      {
        priority: 'HIGH',
        title: 'Fix Missing Image Alt Text',
        detail: `Found ${audit!.images_without_alt} images missing alternative text. Alt text improves accessibility and helps Google Image search index your content.`
      },
      {
        priority: 'MEDIUM',
        title: 'Optimize Title Tag Length',
        detail: `Title tag length is currently ${audit!.title_length} characters. Keep titles between 50-60 characters to avoid truncation in Google SERPs.`
      },
      {
        priority: 'LOW',
        title: 'Add OpenGraph Social Meta Tags',
        detail: 'Ensure og:title, og:description, and og:image are specified for enhanced social sharing snippets on Twitter and LinkedIn.'
      }
    ]
  });
});

// Rank Tracker
app.post('/api/v1/rank/check', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { keyword, domain, website_id } = req.body;
  if (!keyword || (!domain && !website_id)) {
    return res.status(400).json({ error: 'keyword and domain or website_id are required' });
  }

  if (website_id) {
    const { status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  }
  if (domain) {
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Cannot check ranking on another user\'s website' });
  }

  const pos = Math.floor(Math.random() * 12) + 1;
  res.json({
    keyword,
    domain,
    position: pos,
    checked_results: 30,
    source: 'duckduckgo_free'
  });
});

// Leads & Outreach
app.get('/api/v1/leads/:website_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.website_id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const siteLeads = leads.filter(l => l.website_id === websiteId && l.user_id === req.user!.id);
  res.json(siteLeads);
});

app.post('/api/v1/outreach/email/send', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { to_email, subject, body, website_id } = req.body;
  if (website_id) {
    const { status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  }
  res.json({ status: 'sent', to: to_email, subject, timestamp: new Date().toISOString() });
});

// Reports & Export
app.get('/api/v1/reports/:website_id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const websiteId = parseInt(req.params.website_id, 10);
  const { status } = checkWebsiteOwnership(websiteId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });

  const userReports = reports.filter(r => r.website_id === websiteId && r.user_id === req.user!.id);
  res.json(userReports);
});

app.post('/api/v1/reports/export', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { website_id, format = 'pdf' } = req.body;
  if (!website_id) return res.status(400).json({ error: 'website_id is required' });

  const { website, status } = checkWebsiteOwnership(parseInt(website_id, 10), req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Website not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this report' });

  res.json({
    status: 'exported',
    website_id: website!.id,
    domain: website!.domain,
    format,
    download_url: `/api/v1/reports/download/${website!.id}.${format}`,
    timestamp: new Date().toISOString()
  });
});

// Keywords & Domain Metrics
app.post('/api/v1/keywords', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { seed_keyword, limit = 10 } = req.body;
  if (!seed_keyword) {
    return res.status(400).json({ error: 'seed_keyword is required' });
  }

  const base = seed_keyword.toLowerCase();
  const variations = [
    { kw: `${base}`, intent: 'Informational', volume: 14200, kd: 38, cpc: 2.45, cluster: 'Core Concept' },
    { kw: `best ${base} 2026`, intent: 'Commercial', volume: 8900, kd: 52, cpc: 4.80, cluster: 'Best Tools' },
    { kw: `how to set up ${base}`, intent: 'Informational', volume: 6400, kd: 29, cpc: 1.20, cluster: 'Guides & Setup' },
    { kw: `free ${base} audit`, intent: 'Transactional', volume: 5100, kd: 44, cpc: 3.90, cluster: 'Free Services' },
    { kw: `${base} vs traditional audit`, intent: 'Commercial', volume: 3200, kd: 35, cpc: 3.10, cluster: 'Comparisons' },
    { kw: `${base} software for agencies`, intent: 'Transactional', volume: 2800, kd: 48, cpc: 6.50, cluster: 'Agency Solutions' },
    { kw: `${base} python fast api`, intent: 'Informational', volume: 1900, kd: 22, cpc: 0.85, cluster: 'Technical Specs' },
    { kw: `${base} pricing model`, intent: 'Navigational', volume: 1500, kd: 31, cpc: 2.10, cluster: 'Pricing' },
  ];

  res.json(variations.slice(0, limit));
});

app.post('/api/v1/metrics/domain', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { domain } = req.body;
  if (!domain) return res.status(400).json({ error: 'Domain is required' });

  const { status } = checkDomainOwnership(domain, req.user!.id);
  if (status === 403) return res.status(403).json({ error: 'Forbidden: Cannot access metrics for another user\'s domain' });

  const cleanDomain = domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
  res.json({
    domain: cleanDomain,
    provider: 'whois_free',
    domain_age_days: 1845,
    registrar: 'NameCheap Inc.',
    domain_authority: 54,
    backlinks_estimate: 12800,
    organic_traffic_monthly: 42500,
    extra: {
      dns_sec: true,
      ssl_valid: true,
      server_country: 'United States'
    }
  });
});

// Background Job Endpoints
app.post('/api/v1/jobs/crawl', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (!url && !website_id) return res.status(400).json({ error: 'URL or website_id is required' });

  let websiteIdNum: number | undefined;
  if (website_id) {
    websiteIdNum = parseInt(website_id, 10);
    const { status } = checkWebsiteOwnership(websiteIdNum, req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (url) {
    const domain = url.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    website_id: websiteIdNum,
    job_type: 'crawl',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { url, website_id } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { website_id: websiteIdNum || 1, status: 'scraped' };
  }, 50);

  res.json(job);
});

app.post('/api/v1/jobs/audit', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { url, website_id } = req.body;
  if (!url && !website_id) return res.status(400).json({ error: 'URL or website_id is required' });

  let websiteIdNum: number | undefined;
  if (website_id) {
    websiteIdNum = parseInt(website_id, 10);
    const { status } = checkWebsiteOwnership(websiteIdNum, req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (url) {
    const domain = url.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    website_id: websiteIdNum,
    job_type: 'audit',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { url, website_id } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { website_id: websiteIdNum || 1, score: 88 };
  }, 50);

  res.json(job);
});

app.post('/api/v1/jobs/keywords', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { seed_keyword, limit = 10 } = req.body;
  if (!seed_keyword) return res.status(400).json({ error: 'seed_keyword is required' });

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    job_type: 'keywords',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { seed_keyword, limit } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { seed_keyword, count: limit };
  }, 50);

  res.json(job);
});

app.post('/api/v1/jobs/rank', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const { keyword, domain, website_id } = req.body;
  if (!keyword || (!domain && !website_id)) {
    return res.status(400).json({ error: 'keyword and domain or website_id are required' });
  }

  let websiteIdNum: number | undefined;
  if (website_id) {
    websiteIdNum = parseInt(website_id, 10);
    const { status } = checkWebsiteOwnership(websiteIdNum, req.user!.id);
    if (status === 404) return res.status(404).json({ error: 'Website not found' });
    if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this website' });
  } else if (domain) {
    const { status } = checkDomainOwnership(domain, req.user!.id);
    if (status === 403) return res.status(403).json({ error: 'Forbidden: Domain belongs to another user' });
  }

  const job: JobRecord = {
    id: jobs.length + 1,
    user_id: req.user!.id,
    website_id: websiteIdNum,
    job_type: 'rank',
    status: 'pending',
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    result_reference: { payload: { keyword, domain, website_id } }
  };
  jobs.push(job);

  setTimeout(() => {
    job.status = 'completed';
    job.progress = 100;
    job.started_at = new Date().toISOString();
    job.finished_at = new Date().toISOString();
    job.result_reference = { keyword, position: 4 };
  }, 50);

  res.json(job);
});

app.get('/api/v1/jobs', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  let userJobs = jobs.filter(j => j.user_id === req.user!.id);
  const { job_type, status, website_id } = req.query;
  if (job_type) userJobs = userJobs.filter(j => j.job_type === job_type);
  if (status) userJobs = userJobs.filter(j => j.status === status);
  if (website_id) userJobs = userJobs.filter(j => j.website_id === parseInt(website_id as string, 10));

  res.json(userJobs);
});

app.get('/api/v1/jobs/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const jobId = parseInt(req.params.id, 10);
  const { job, status } = checkJobOwnership(jobId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Job not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this job' });
  res.json(job);
});

app.delete('/api/v1/jobs/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const jobId = parseInt(req.params.id, 10);
  const { status } = checkJobOwnership(jobId, req.user!.id);
  if (status === 404) return res.status(404).json({ error: 'Job not found' });
  if (status === 403) return res.status(403).json({ error: 'Forbidden: You do not own this job' });

  const idx = jobs.findIndex(j => j.id === jobId);
  if (idx !== -1) jobs.splice(idx, 1);
  res.json({ message: 'Job deleted successfully', id: jobId });
});

// --- VITE MIDDLEWARE & SERVER STARTUP ---

async function startServer() {
  if (process.env.NODE_ENV !== 'production' && process.env.NODE_ENV !== 'test') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else if (process.env.NODE_ENV === 'production') {
    const distPath = path.resolve(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.resolve(distPath, 'index.html'));
    });
  }

  if (process.env.NODE_ENV !== 'test') {
    app.listen(PORT, '0.0.0.0', () => {
      console.log(`SEO Agent server listening on port ${PORT}`);
    });
  }
}

startServer();
