import React, { useState } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
  Download,
  FileSpreadsheet,
  Globe,
  RefreshCw,
  ExternalLink,
  Info,
  Layers,
  Sparkles
} from 'lucide-react';
import { AuditResult, Website } from '../types';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';

interface TechnicalAuditProps {
  audits: AuditResult[];
  websites: Website[];
  onRunAudit: (url: string) => void;
  isLoading: boolean;
  onOpenAIAdvisor: () => void;
}

export const TechnicalAudit: React.FC<TechnicalAuditProps> = ({
  audits,
  websites,
  onRunAudit,
  isLoading,
  onOpenAIAdvisor
}) => {
  const [urlInput, setUrlInput] = useState('https://techflow-seo.com');
  const [selectedAuditId, setSelectedAuditId] = useState<number | null>(
    audits.length > 0 ? audits[0].id : null
  );
  const [activeFilter, setActiveFilter] = useState<'all' | 'errors' | 'warnings' | 'passed'>('all');

  const currentAudit = audits.find((a) => a.id === selectedAuditId) || audits[audits.length - 1];
  const currentWebsite = websites.find((w) => w.id === currentAudit?.website_id) || websites[0];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlInput.trim()) {
      onRunAudit(urlInput.trim());
    }
  };

  // Build audit issues list for display
  const auditChecks = currentAudit
    ? [
        {
          id: 'title',
          name: 'Title Tag Optimization',
          category: 'Meta & Headings',
          status: currentAudit.title_length && currentAudit.title_length >= 50 && currentAudit.title_length <= 60 ? 'passed' : 'warning',
          detail: `Title: "${currentAudit.title}" (${currentAudit.title_length || 0} chars). Recommended: 50-60 characters.`,
          recommendation: 'Keep main title concise and include primary target keyword near the start.'
        },
        {
          id: 'meta_description',
          name: 'Meta Description Tag',
          category: 'Meta & Headings',
          status: currentAudit.meta_description_length && currentAudit.meta_description_length >= 120 && currentAudit.meta_description_length <= 160 ? 'passed' : 'passed',
          detail: `Meta Description: "${currentAudit.meta_description}" (${currentAudit.meta_description_length || 0} chars).`,
          recommendation: 'Good length. Ensure compelling call-to-action for higher search CTR.'
        },
        {
          id: 'h1_structure',
          name: 'H1 Tag Hierarchy',
          category: 'Meta & Headings',
          status: currentAudit.h1_tags && currentAudit.h1_tags.length === 1 ? 'passed' : 'warning',
          detail: `Found ${currentAudit.h1_tags?.length || 0} H1 tag: "${currentAudit.h1_tags?.[0] || 'None'}".`,
          recommendation: 'Every page should contain exactly one H1 tag matching primary page intent.'
        },
        {
          id: 'viewport',
          name: 'Mobile Viewport Tag',
          category: 'Technical & Mobile',
          status: currentAudit.viewport ? 'passed' : 'error',
          detail: `Viewport content: "${currentAudit.viewport || 'Missing'}"`,
          recommendation: 'Ensures proper mobile rendering across mobile devices and tablets.'
        },
        {
          id: 'alt_text',
          name: 'Image Alternative Text',
          category: 'Content & Accessibility',
          status: currentAudit.images_without_alt > 0 ? 'error' : 'passed',
          detail: `${currentAudit.images_without_alt} of ${currentAudit.images_count} images missing alt text attributes.`,
          recommendation: 'Add descriptive alt tags to all informative images to rank in Google Images.'
        },
        {
          id: 'sitemap',
          name: 'XML Sitemap Availability',
          category: 'Crawlability',
          status: currentAudit.has_sitemap ? 'passed' : 'error',
          detail: 'sitemap.xml found and validated at /sitemap.xml',
          recommendation: 'Sitemap allows search engine crawlers to index deep page structures.'
        },
        {
          id: 'robots',
          name: 'Robots.txt Directive',
          category: 'Crawlability',
          status: currentAudit.has_robots_txt ? 'passed' : 'warning',
          detail: 'robots.txt found with valid allow directives.',
          recommendation: 'Verify search bots are not accidentally blocked from key landing pages.'
        },
        {
          id: 'structured_data',
          name: 'Structured Data (JSON-LD)',
          category: 'Rich Snippets',
          status: currentAudit.has_structured_data ? 'passed' : 'warning',
          detail: 'Schema.org JSON-LD markup detected for WebSite and Organization.',
          recommendation: 'Improves rich search results with star ratings, FAQs, and organization info.'
        },
        {
          id: 'broken_links',
          name: 'Broken Hyperlinks (404)',
          category: 'Crawlability',
          status: currentAudit.broken_links_count > 0 ? 'error' : 'passed',
          detail: `${currentAudit.broken_links_count} broken links detected across crawl scope.`,
          recommendation: 'Fix or redirect broken URLs to avoid link equity decay.'
        }
      ]
    : [];

  const filteredChecks = auditChecks.filter((check) => {
    if (activeFilter === 'errors') return check.status === 'error';
    if (activeFilter === 'warnings') return check.status === 'warning';
    if (activeFilter === 'passed') return check.status === 'passed';
    return true;
  });

  // Export handlers
  const exportCSV = () => {
    if (!currentAudit) return;
    const rows = auditChecks.map((c) => ({
      Check: c.name,
      Category: c.category,
      Status: c.status.toUpperCase(),
      Details: c.detail,
      Recommendation: c.recommendation
    }));

    const worksheet = XLSX.utils.json_to_sheet(rows);
    const csvContent = XLSX.utils.sheet_to_csv(worksheet);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `SEO_Audit_${currentWebsite?.domain || 'site'}.csv`;
    link.click();
  };

  const exportXLSX = () => {
    if (!currentAudit) return;
    const rows = auditChecks.map((c) => ({
      Check: c.name,
      Category: c.category,
      Status: c.status.toUpperCase(),
      Details: c.detail,
      Recommendation: c.recommendation
    }));

    const worksheet = XLSX.utils.json_to_sheet(rows);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Technical Audit');
    XLSX.writeFile(workbook, `SEO_Audit_${currentWebsite?.domain || 'site'}.xlsx`);
  };

  const exportPDF = () => {
    if (!currentAudit) return;
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text(`Technical SEO Audit Report`, 14, 20);
    doc.setFontSize(12);
    doc.text(`Domain: ${currentWebsite?.url || 'Site'}`, 14, 28);
    doc.text(`Overall Score: ${currentAudit.score}/100`, 14, 34);
    doc.text(`Generated: ${new Date().toLocaleDateString()}`, 14, 40);

    const tableData = auditChecks.map((c) => [
      c.name,
      c.category,
      c.status.toUpperCase(),
      c.detail
    ]);

    autoTable(doc, {
      startY: 46,
      head: [['Check Name', 'Category', 'Status', 'Audit Details']],
      body: tableData,
      theme: 'grid',
      headStyles: { fillColor: [15, 23, 42] }
    });

    doc.save(`SEO_Audit_${currentWebsite?.domain || 'site'}.pdf`);
  };

  return (
    <div className="space-y-6">
      {/* Header Form */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <ShieldCheck className="h-6 w-6 text-cyan-400" />
              <span>Technical SEO Audit Engine</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Full site audit covering crawlability, metadata, structured data, mobile compliance, and broken links.
            </p>
          </div>

          {/* Export Dropdown / Buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={exportCSV}
              className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              <span>CSV</span>
            </button>
            <button
              onClick={exportXLSX}
              className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              <FileSpreadsheet className="h-3.5 w-3.5" />
              <span>Excel</span>
            </button>
            <button
              onClick={exportPDF}
              className="px-3 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow-md transition-all"
            >
              <FileText className="h-3.5 w-3.5" />
              <span>PDF Report</span>
            </button>
          </div>
        </div>

        {/* Form input */}
        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Globe className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Enter domain or URL to audit..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-sm rounded-xl transition-colors flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 disabled:opacity-50"
          >
            {isLoading ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <ShieldCheck className="h-4 w-4" />
            )}
            <span>{isLoading ? 'Crawling...' : 'Audit Target URL'}</span>
          </button>
        </form>
      </div>

      {currentAudit && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Audit Score Card */}
          <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 flex flex-col items-center justify-center text-center">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Technical Health Score</p>
            <div className="relative flex items-center justify-center my-4">
              <div className="h-36 w-36 rounded-full border-8 border-slate-800 flex items-center justify-center">
                <div className="text-center">
                  <span className="text-4xl font-extrabold text-white">{currentAudit.score}</span>
                  <span className="text-xs text-slate-400 block font-mono">/100</span>
                </div>
              </div>
            </div>
            <div className="w-full space-y-2 text-xs text-slate-300">
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Audited Domain:</span>
                <span className="font-mono text-white font-medium">{currentWebsite?.domain}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Total Images Audited:</span>
                <span className="font-mono text-white font-medium">{currentAudit.images_count}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-400">Broken Links:</span>
                <span className={`font-mono font-medium ${currentAudit.broken_links_count > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {currentAudit.broken_links_count}
                </span>
              </div>
            </div>

            <button
              onClick={onOpenAIAdvisor}
              className="mt-6 w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-cyan-400 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 border border-cyan-500/20 transition-all"
            >
              <Sparkles className="h-4 w-4" />
              <span>Get AI Optimization Steps</span>
            </button>
          </div>

          {/* Audit Checks Table & Filter */}
          <div className="lg:col-span-2 bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white">Diagnostic Checks</h3>
                <p className="text-xs text-slate-400">Detailed line-by-line inspection breakdown</p>
              </div>

              {/* Filters */}
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
                {(['all', 'errors', 'warnings', 'passed'] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setActiveFilter(filter)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition-colors ${
                      activeFilter === filter
                        ? 'bg-slate-800 text-cyan-400 font-semibold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {/* List of Checks */}
            <div className="space-y-3">
              {filteredChecks.map((check) => (
                <div
                  key={check.id}
                  className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 hover:border-slate-700 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {check.status === 'passed' && <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />}
                      {check.status === 'warning' && <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />}
                      {check.status === 'error' && <XCircle className="h-4 w-4 text-rose-400 shrink-0" />}
                      <span className="font-bold text-white text-sm">{check.name}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                        {check.category}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 pl-6 leading-relaxed">{check.detail}</p>
                    <p className="text-[11px] text-slate-500 pl-6 flex items-center gap-1 mt-1">
                      <Info className="h-3 w-3 text-cyan-500/80" />
                      <span>{check.recommendation}</span>
                    </p>
                  </div>

                  <span
                    className={`px-3 py-1 rounded-full text-xs font-mono font-bold uppercase shrink-0 ${
                      check.status === 'passed'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : check.status === 'warning'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}
                  >
                    {check.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
