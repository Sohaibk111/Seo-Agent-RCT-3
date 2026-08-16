import React, { useState } from 'react';
import { Sparkles, AlertTriangle, CheckCircle2, ChevronRight, Copy, Check, Code, Lightbulb } from 'lucide-react';
import { AIAnalysis, AuditResult } from '../types';

interface AIRecommendationsProps {
  audit: AuditResult | null;
}

export const AIRecommendations: React.FC<AIRecommendationsProps> = ({ audit }) => {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const recommendations = [
    {
      priority: 'HIGH',
      title: 'Fix Missing Image Alt Attributes',
      detail: `Detected ${audit?.images_without_alt || 2} images lacking alt attributes. Alternative text is critical for accessibility and enables indexing in Google Image Search.`,
      codeSnippet: `<img src="/assets/hero-banner.png" alt="TechFlow AI SEO Automation Platform Interface" />`
    },
    {
      priority: 'MEDIUM',
      title: 'Optimize Title Tag Character Count',
      detail: `Your title tag contains ${audit?.title_length || 68} characters. Search engines truncate titles exceeding 60 characters with an ellipsis (...) in SERP snippets.`,
      codeSnippet: `<title>TechFlow - AI SEO Automation & Keyword Intelligence Platform</title>`
    },
    {
      priority: 'LOW',
      title: 'Implement Organization & WebSite JSON-LD Schema',
      detail: 'Adding structured data schema enables rich snippets, site search boxes, and knowledge graph panels in Google Search results.',
      codeSnippet: `<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "TechFlow SEO Agent",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web"
}
</script>`
    }
  ];

  const handleCopy = (snippet: string, idx: number) => {
    navigator.clipboard.writeText(snippet);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-indigo-950 via-slate-900 to-slate-900 rounded-2xl border border-indigo-500/30 p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400">
            <Sparkles className="h-6 w-6" />
          </div>
          <h2 className="text-xl font-bold text-white">AI SEO Optimization Advisor</h2>
        </div>
        <p className="text-slate-300 text-sm max-w-3xl leading-relaxed">
          Powered by Gemini AI analysis. Our rule engine inspects technical crawling results, keyword density, metadata health, and schema validation to deliver prioritized fix guides.
        </p>
      </div>

      {/* Summary Box */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-amber-400" />
          <span>Executive Audit Summary</span>
        </h3>
        <p className="text-white text-sm leading-relaxed">
          The technical audit for Audit #{audit?.id || 101} yielded an overall health score of{' '}
          <span className="font-bold text-cyan-400 font-mono">{audit?.score || 84}/100</span>. Core title and canonical tags are healthy, but image alt attributes and broken link monitoring present immediate high-impact quick wins.
        </p>
      </div>

      {/* Actionable Recommendations */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-white">Prioritized Action Plan</h3>

        {recommendations.map((rec, idx) => (
          <div
            key={idx}
            className="bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4 hover:border-slate-700 transition-colors"
          >
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span
                  className={`px-3 py-1 rounded-full text-xs font-mono font-bold uppercase ${
                    rec.priority === 'HIGH'
                      ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                      : rec.priority === 'MEDIUM'
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                      : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  }`}
                >
                  {rec.priority} Priority
                </span>
                <h4 className="text-base font-bold text-white">{rec.title}</h4>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">{rec.detail}</p>

            {/* Code Snippet Box */}
            <div className="bg-slate-950 rounded-xl border border-slate-800 p-4 relative group">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span className="font-mono flex items-center gap-1">
                  <Code className="h-3.5 w-3.5 text-cyan-400" />
                  Recommended Fix Snippet
                </span>
                <button
                  onClick={() => handleCopy(rec.codeSnippet, idx)}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs flex items-center gap-1 transition-colors"
                >
                  {copiedIdx === idx ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy Code</span>
                    </>
                  )}
                </button>
              </div>

              <pre className="font-mono text-xs text-cyan-300 overflow-x-auto whitespace-pre-wrap">
                {rec.codeSnippet}
              </pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
