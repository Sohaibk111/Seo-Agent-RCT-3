import React, { useState } from 'react';
import {
  Search,
  Sparkles,
  Layers,
  Download,
  DollarSign,
  TrendingUp,
  Tag,
  Filter
} from 'lucide-react';
import { KeywordResult } from '../types';
import * as XLSX from 'xlsx';

export const KeywordPlanner: React.FC = () => {
  const [seedInput, setSeedInput] = useState('seo tools');
  const [isSearching, setIsSearching] = useState(false);
  const [keywords, setKeywords] = useState<KeywordResult[]>([
    { kw: 'seo tools', intent: 'Informational', volume: 14200, kd: 38, cpc: 2.45, cluster: 'Core Concept' },
    { kw: 'best seo tools 2026', intent: 'Commercial', volume: 8900, kd: 52, cpc: 4.80, cluster: 'Best Tools' },
    { kw: 'how to set up seo tools', intent: 'Informational', volume: 6400, kd: 29, cpc: 1.20, cluster: 'Guides & Setup' },
    { kw: 'free seo tools audit', intent: 'Transactional', volume: 5100, kd: 44, cpc: 3.90, cluster: 'Free Services' },
    { kw: 'seo tools vs traditional audit', intent: 'Commercial', volume: 3200, kd: 35, cpc: 3.10, cluster: 'Comparisons' },
    { kw: 'seo tools software for agencies', intent: 'Transactional', volume: 2800, kd: 48, cpc: 6.50, cluster: 'Agency Solutions' },
    { kw: 'seo tools python fast api', intent: 'Informational', volume: 1900, kd: 22, cpc: 0.85, cluster: 'Technical Specs' },
    { kw: 'seo tools pricing model', intent: 'Navigational', volume: 1500, kd: 31, cpc: 2.10, cluster: 'Pricing' },
  ]);

  const [selectedIntent, setSelectedIntent] = useState<string>('all');

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!seedInput.trim()) return;

    setIsSearching(true);
    try {
      const res = await fetch('/api/v1/keywords', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock_jwt_token_sample'
        },
        body: JSON.stringify({ seed_keyword: seedInput.trim(), limit: 10 })
      });
      if (res.ok) {
        const data = await res.json();
        setKeywords(data);
      }
    } catch (err) {
      console.error('Failed to fetch keywords', err);
    } finally {
      setIsSearching(false);
    }
  };

  const filteredKeywords = keywords.filter((k) => {
    if (selectedIntent === 'all') return true;
    return k.intent.toLowerCase() === selectedIntent.toLowerCase();
  });

  const exportCSV = () => {
    const worksheet = XLSX.utils.json_to_sheet(keywords);
    const csvContent = XLSX.utils.sheet_to_csv(worksheet);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `Keywords_${seedInput.replace(/\s+/g, '_')}.csv`;
    link.click();
  };

  // Group keywords by cluster
  const clustersMap = keywords.reduce((acc, k) => {
    acc[k.cluster] = (acc[k.cluster] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Search className="h-6 w-6 text-indigo-400" />
              <span>Keyword Research & Intent Clustering</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Uncover keyword search volume, difficulty, cost-per-click, and automated intent categorization.
            </p>
          </div>

          <button
            onClick={exportCSV}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 flex items-center gap-2 transition-colors self-start sm:self-auto"
          >
            <Download className="h-4 w-4" />
            <span>Export Keywords CSV</span>
          </button>
        </div>

        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={seedInput}
              onChange={(e) => setSeedInput(e.target.value)}
              placeholder="Enter seed keyword (e.g., seo tools, local marketing)..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching}
            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm rounded-xl transition-colors flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20 disabled:opacity-50"
          >
            {isSearching ? (
              <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            <span>Expand & Cluster</span>
          </button>
        </form>
      </div>

      {/* Cluster Overview Badges */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
          <p className="text-xs text-slate-400 uppercase font-medium">Total Keywords</p>
          <p className="text-2xl font-bold text-white mt-1">{keywords.length}</p>
        </div>
        <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
          <p className="text-xs text-slate-400 uppercase font-medium">Total Monthly Volume</p>
          <p className="text-2xl font-bold text-white mt-1">
            {keywords.reduce((a, b) => a + b.volume, 0).toLocaleString()}
          </p>
        </div>
        <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
          <p className="text-xs text-slate-400 uppercase font-medium">Avg Keyword Difficulty</p>
          <p className="text-2xl font-bold text-white mt-1">
            {Math.round(keywords.reduce((a, b) => a + b.kd, 0) / keywords.length)}%
          </p>
        </div>
        <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
          <p className="text-xs text-slate-400 uppercase font-medium">Topic Clusters</p>
          <p className="text-2xl font-bold text-white mt-1">{Object.keys(clustersMap).length}</p>
        </div>
      </div>

      {/* Filter Tabs & Table */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h3 className="text-lg font-bold text-white">Keyword Intelligence Matrix</h3>

          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 overflow-x-auto">
            {['all', 'informational', 'commercial', 'transactional', 'navigational'].map((intent) => (
              <button
                key={intent}
                onClick={() => setSelectedIntent(intent)}
                className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition-colors ${
                  selectedIntent === intent
                    ? 'bg-indigo-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {intent}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/60 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 rounded-l-lg">Keyword Opportunity</th>
                <th className="px-4 py-3">Search Intent</th>
                <th className="px-4 py-3">Topic Cluster</th>
                <th className="px-4 py-3 text-right">Volume</th>
                <th className="px-4 py-3 text-right">KD %</th>
                <th className="px-4 py-3 text-right rounded-r-lg">Est. CPC</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredKeywords.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-3.5 font-medium text-white flex items-center gap-2">
                    <Tag className="h-4 w-4 text-indigo-400" />
                    <span>{item.kw}</span>
                  </td>
                  <td className="px-4 py-3.5">
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-semibold font-mono ${
                        item.intent === 'Transactional'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : item.intent === 'Commercial'
                          ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                          : item.intent === 'Informational'
                          ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {item.intent}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-slate-400">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                      {item.cluster}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-right font-mono font-bold text-white">
                    {item.volume.toLocaleString()}
                  </td>
                  <td className="px-4 py-3.5 text-right">
                    <span
                      className={`font-mono text-xs font-bold ${
                        item.kd > 50 ? 'text-rose-400' : item.kd > 30 ? 'text-amber-400' : 'text-emerald-400'
                      }`}
                    >
                      {item.kd}%
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-right font-mono text-emerald-400 font-medium">
                    ${item.cpc.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
