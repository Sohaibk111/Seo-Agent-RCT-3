import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Navbar, TabType } from './components/Navbar';
import { useTheme } from './hooks/useTheme';
import { AuditResult, Lead, Website } from './types';

// Dynamic route component imports for lazy loading & code splitting
const Overview = lazy(() => import('./components/Overview').then(m => ({ default: m.Overview })));
const TechnicalAudit = lazy(() => import('./components/TechnicalAudit').then(m => ({ default: m.TechnicalAudit })));
const KeywordPlanner = lazy(() => import('./components/KeywordPlanner').then(m => ({ default: m.KeywordPlanner })));
const DomainMetrics = lazy(() => import('./components/DomainMetrics').then(m => ({ default: m.DomainMetrics })));
const RankTracker = lazy(() => import('./components/RankTracker').then(m => ({ default: m.RankTracker })));
const LeadOutreach = lazy(() => import('./components/LeadOutreach').then(m => ({ default: m.LeadOutreach })));
const AIRecommendations = lazy(() => import('./components/AIRecommendations').then(m => ({ default: m.AIRecommendations })));

// Tab component prefetch dictionary
const tabPrefetchers: Record<TabType, () => Promise<unknown>> = {
  overview: () => import('./components/Overview'),
  audit: () => import('./components/TechnicalAudit'),
  keywords: () => import('./components/KeywordPlanner'),
  metrics: () => import('./components/DomainMetrics'),
  rank: () => import('./components/RankTracker'),
  leads: () => import('./components/LeadOutreach'),
  ai: () => import('./components/AIRecommendations'),
};

const LoadingFallback: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-[300px] gap-3 text-slate-400 py-12">
    <div className="h-8 w-8 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin"></div>
    <span className="text-sm font-medium animate-pulse">Loading view assets...</span>
  </div>
);

export function App() {
  const { theme, toggleTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [websites, setWebsites] = useState<Website[]>([
    { id: 1, url: 'https://techflow-seo.com', domain: 'techflow-seo.com', company_name: 'TechFlow Inc.', created_at: new Date().toISOString() },
    { id: 2, url: 'https://acme-analytics.io', domain: 'acme-analytics.io', company_name: 'Acme Analytics', created_at: new Date().toISOString() }
  ]);
  const [audits, setAudits] = useState<AuditResult[]>([
    {
      id: 101,
      website_id: 1,
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
  ]);
  const [leads, setLeads] = useState<Lead[]>([
    { id: 1, website_id: 1, email: 'contact@techflow-seo.com', phone: '+1 (555) 234-5678', source: 'footer_scrape' },
    { id: 2, website_id: 1, email: 'growth@techflow-seo.com', source: 'meta_contacts' }
  ]);
  const [isLoadingAudit, setIsLoadingAudit] = useState(false);

  // Prefetch handler for dynamic route preloading
  const handlePrefetchTab = (tab: TabType) => {
    if (tabPrefetchers[tab]) {
      tabPrefetchers[tab]().catch(() => {});
    }
  };

  // Idle prefetching strategy for secondary routes
  useEffect(() => {
    const prefetchSecondaryRoutes = () => {
      const secondaryTabs: TabType[] = ['audit', 'keywords', 'metrics', 'rank', 'leads', 'ai'];
      secondaryTabs.forEach((tab) => {
        tabPrefetchers[tab]().catch(() => {});
      });
    };

    if ('requestIdleCallback' in window) {
      (window as unknown as { requestIdleCallback: (cb: () => void) => void }).requestIdleCallback(prefetchSecondaryRoutes);
    } else {
      setTimeout(prefetchSecondaryRoutes, 2000);
    }
  }, []);

  // Initial fetch from backend if available
  useEffect(() => {
    fetch('/api/v1/websites', {
      headers: { 'Authorization': 'Bearer mock_jwt_token_sample' }
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data) && data.length > 0) {
          setWebsites(data);
        }
      })
      .catch((err) => console.log('Using default mock websites', err));
  }, []);

  const handleRunAudit = async (url: string) => {
    setIsLoadingAudit(true);
    try {
      const res = await fetch('/api/v1/audit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock_jwt_token_sample'
        },
        body: JSON.stringify({ url })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.website) setWebsites((prev) => [data.website, ...prev]);
        if (data.audit) setAudits((prev) => [data.audit, ...prev]);
        if (data.leads_found > 0) {
          const domain = data.website?.domain || 'target.com';
          setLeads((prev) => [
            { id: prev.length + 1, website_id: data.website?.id || 1, email: `info@${domain}`, source: 'domain_audit' },
            ...prev
          ]);
        }
        setActiveTab('audit');
      }
    } catch (err) {
      console.error('Audit failed', err);
    } finally {
      setIsLoadingAudit(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onPrefetchTab={handlePrefetchTab}
        auditCount={audits.length}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Suspense fallback={<LoadingFallback />}>
          {activeTab === 'overview' && (
            <Overview
              onRunAudit={handleRunAudit}
              isLoadingAudit={isLoadingAudit}
              websites={websites}
              audits={audits}
              setActiveTab={setActiveTab}
            />
          )}

          {activeTab === 'audit' && (
            <TechnicalAudit
              audits={audits}
              websites={websites}
              onRunAudit={handleRunAudit}
              isLoading={isLoadingAudit}
              onOpenAIAdvisor={() => setActiveTab('ai')}
            />
          )}

          {activeTab === 'keywords' && <KeywordPlanner />}

          {activeTab === 'metrics' && <DomainMetrics />}

          {activeTab === 'rank' && <RankTracker />}

          {activeTab === 'leads' && <LeadOutreach leads={leads} websites={websites} />}

          {activeTab === 'ai' && <AIRecommendations audit={audits[0] || null} />}
        </Suspense>
      </main>

      <footer className="border-t border-slate-800 bg-slate-900/50 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>© 2026 SEO Agent — Technical Audit & Keyword Intelligence Platform</p>
          <div className="flex items-center gap-4">
            <span>FastAPI Backend</span>
            <span>•</span>
            <span>Playwright Engine</span>
            <span>•</span>
            <span>Alembic DB</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
