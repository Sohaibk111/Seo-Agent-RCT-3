import React, { useState } from 'react';
import {
  ShieldCheck,
  Search,
  Zap,
  Mail,
  ArrowRight,
  TrendingUp,
  FileCheck2,
  AlertTriangle,
  Globe,
  Sparkles,
  CheckCircle2
} from 'lucide-react';
import { AuditResult, Website } from '../types';
import { TabType } from './Navbar';

interface OverviewProps {
  onRunAudit: (url: string) => void;
  isLoadingAudit: boolean;
  websites: Website[];
  audits: AuditResult[];
  setActiveTab: (tab: TabType) => void;
}

export const Overview: React.FC<OverviewProps> = ({
  onRunAudit,
  isLoadingAudit,
  websites,
  audits,
  setActiveTab
}) => {
  const [urlInput, setUrlInput] = useState('https://techflow-seo.com');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlInput.trim()) {
      onRunAudit(urlInput.trim());
    }
  };

  const latestAudit = audits.length > 0 ? audits[audits.length - 1] : null;

  return (
    <div className="space-y-8">
      {/* Hero Quick Audit Section */}
      <div className="relative rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 p-6 sm:p-8 border border-slate-800 shadow-xl overflow-hidden">
        <div className="absolute -right-20 -top-20 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-semibold mb-4">
            <Sparkles className="h-3.5 w-3.5" />
            <span>AI-POWERED TECHNICAL AUDIT ENGINE</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Analyze, Audit, & Scale Your Search Visibility
          </h1>
          <p className="mt-3 text-slate-300 text-sm sm:text-base leading-relaxed">
            Run complete technical audits, discover high-intent keywords, track SERP ranks, extract lead contacts, and generate AI recommendations in seconds.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Globe className="absolute left-3.5 top-3.5 h-5 w-5 text-slate-400" />
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="Enter website URL (e.g., https://example.com)"
                className="w-full pl-11 pr-4 py-3 bg-slate-950 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 text-sm font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={isLoadingAudit}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-sm hover:from-cyan-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-cyan-400/50 transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 disabled:opacity-50"
            >
              {isLoadingAudit ? (
                <>
                  <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  <span>Auditing...</span>
                </>
              ) : (
                <>
                  <span>Run Site Audit</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 p-5 rounded-xl border border-slate-800 flex items-center gap-4">
          <div className="h-12 w-12 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <FileCheck2 className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Audited Websites</p>
            <p className="text-2xl font-bold text-white mt-0.5">{websites.length}</p>
          </div>
        </div>

        <div className="bg-slate-900 p-5 rounded-xl border border-slate-800 flex items-center gap-4">
          <div className="h-12 w-12 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <TrendingUp className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Avg SEO Score</p>
            <p className="text-2xl font-bold text-white mt-0.5">
              {latestAudit ? `${latestAudit.score}/100` : '84/100'}
            </p>
          </div>
        </div>

        <div className="bg-slate-900 p-5 rounded-xl border border-slate-800 flex items-center gap-4">
          <div className="h-12 w-12 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Search className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Keywords Expanded</p>
            <p className="text-2xl font-bold text-white mt-0.5">142+</p>
          </div>
        </div>

        <div className="bg-slate-900 p-5 rounded-xl border border-slate-800 flex items-center gap-4">
          <div className="h-12 w-12 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <Mail className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Leads & Contacts</p>
            <p className="text-2xl font-bold text-white mt-0.5">18 Found</p>
          </div>
        </div>
      </div>

      {/* Core Tool Access Grid */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-white">Platform Modules</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Module 1: Technical Audit */}
          <div
            onClick={() => setActiveTab('audit')}
            className="group cursor-pointer bg-slate-900 hover:bg-slate-800/80 p-6 rounded-2xl border border-slate-800 hover:border-cyan-500/50 transition-all shadow-lg"
          >
            <div className="h-12 w-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4 group-hover:scale-110 transition-transform">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-bold text-white flex items-center justify-between">
              <span>Technical SEO Audit</span>
              <ArrowRight className="h-4 w-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
            </h3>
            <p className="text-slate-400 text-sm mt-2 leading-relaxed">
              Crawl pages for meta tags, H1 structure, canonical tags, mobile viewports, image alt attributes, broken links, and structured data.
            </p>
            <div className="mt-4 flex items-center gap-2 text-xs font-medium text-cyan-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Sitemap & Robots.txt Verification</span>
            </div>
          </div>

          {/* Module 2: Keyword Planner */}
          <div
            onClick={() => setActiveTab('keywords')}
            className="group cursor-pointer bg-slate-900 hover:bg-slate-800/80 p-6 rounded-2xl border border-slate-800 hover:border-indigo-500/50 transition-all shadow-lg"
          >
            <div className="h-12 w-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 group-hover:scale-110 transition-transform">
              <Search className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-bold text-white flex items-center justify-between">
              <span>Keyword Intent & Clustering</span>
              <ArrowRight className="h-4 w-4 text-slate-500 group-hover:text-indigo-400 transition-colors" />
            </h3>
            <p className="text-slate-400 text-sm mt-2 leading-relaxed">
              Expand seed keywords into high-volume opportunities with search intent tagging (Informational, Transactional) and token clustering.
            </p>
            <div className="mt-4 flex items-center gap-2 text-xs font-medium text-indigo-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Difficulty & CPC Estimates</span>
            </div>
          </div>

          {/* Module 3: Rank Tracker */}
          <div
            onClick={() => setActiveTab('rank')}
            className="group cursor-pointer bg-slate-900 hover:bg-slate-800/80 p-6 rounded-2xl border border-slate-800 hover:border-emerald-500/50 transition-all shadow-lg"
          >
            <div className="h-12 w-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4 group-hover:scale-110 transition-transform">
              <Zap className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-bold text-white flex items-center justify-between">
              <span>SERP Rank Tracker</span>
              <ArrowRight className="h-4 w-4 text-slate-500 group-hover:text-emerald-400 transition-colors" />
            </h3>
            <p className="text-slate-400 text-sm mt-2 leading-relaxed">
              Track domain rankings across target keywords with real-time SERP position monitoring and competitive benchmarking.
            </p>
            <div className="mt-4 flex items-center gap-2 text-xs font-medium text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>DuckDuckGo & Search Verification</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Websites Table */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-white">Recent Audited Websites</h3>
            <p className="text-xs text-slate-400">Manage audited domains and review saved reports</p>
          </div>
          <button
            onClick={() => setActiveTab('audit')}
            className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <span>View All Audits</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/60 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 rounded-l-lg">Domain / Company</th>
                <th className="px-4 py-3">Audit Score</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Audited Date</th>
                <th className="px-4 py-3 text-right rounded-r-lg">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {websites.map((site) => {
                const siteAudit = audits.find((a) => a.website_id === site.id);
                const score = siteAudit?.score || 84;
                return (
                  <tr key={site.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-4 font-medium text-white">
                      <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-slate-400" />
                        <div>
                          <p className="font-semibold text-white">{site.domain}</p>
                          <p className="text-xs text-slate-400">{site.company_name || 'Organization'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-block px-2.5 py-1 rounded-full text-xs font-bold font-mono ${
                            score >= 80
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : score >= 60
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          }`}
                        >
                          {score}/100
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                        Healthy
                      </span>
                    </td>
                    <td className="px-4 py-4 text-xs text-slate-400 font-mono">
                      {new Date(site.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <button
                        onClick={() => setActiveTab('audit')}
                        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium transition-colors"
                      >
                        Inspect Audit
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
