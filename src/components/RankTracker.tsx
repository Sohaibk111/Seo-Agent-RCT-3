import React, { useState } from 'react';
import { Zap, Search, Globe, TrendingUp, CheckCircle2, ArrowUpRight, Award } from 'lucide-react';
import { RankResult } from '../types';

export const RankTracker: React.FC = () => {
  const [domainInput, setDomainInput] = useState('techflow-seo.com');
  const [keywordInput, setKeywordInput] = useState('seo tools');
  const [isChecking, setIsChecking] = useState(false);
  const [trackedRanks, setTrackedRanks] = useState<RankResult[]>([
    { keyword: 'seo tools', domain: 'techflow-seo.com', position: 4, checked_results: 30, source: 'duckduckgo_free' },
    { keyword: 'technical seo audit', domain: 'techflow-seo.com', position: 2, checked_results: 30, source: 'duckduckgo_free' },
    { keyword: 'keyword clustering engine', domain: 'techflow-seo.com', position: 1, checked_results: 30, source: 'duckduckgo_free' },
    { keyword: 'automated rank tracking', domain: 'techflow-seo.com', position: 7, checked_results: 30, source: 'duckduckgo_free' },
  ]);

  const handleCheckRank = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keywordInput.trim() || !domainInput.trim()) return;

    setIsChecking(true);
    try {
      const res = await fetch('/api/v1/rank/check', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock_jwt_token_sample'
        },
        body: JSON.stringify({ keyword: keywordInput.trim(), domain: domainInput.trim() })
      });
      if (res.ok) {
        const data = await res.json();
        setTrackedRanks((prev) => [data, ...prev.filter((r) => r.keyword !== data.keyword)]);
      }
    } catch (err) {
      console.error('Failed to check rank', err);
    } finally {
      setIsChecking(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Zap className="h-6 w-6 text-emerald-400" />
            <span>SERP Rank Position Tracker</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Check exact SERP search position for target domain and keyword pairs across search results.
          </p>
        </div>

        <form onSubmit={handleCheckRank} className="grid grid-cols-1 sm:grid-cols-5 gap-3">
          <div className="relative sm:col-span-2">
            <Globe className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              placeholder="Target Domain..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            />
          </div>
          <div className="relative sm:col-span-2">
            <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              placeholder="Target Keyword..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            />
          </div>
          <button
            type="submit"
            disabled={isChecking}
            className="sm:col-span-1 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm rounded-xl transition-colors flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 disabled:opacity-50"
          >
            {isChecking ? (
              <div className="h-4 w-4 border-2 border-black border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <Zap className="h-4 w-4" />
            )}
            <span>Check Rank</span>
          </button>
        </form>
      </div>

      {/* Tracked Keywords Grid */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
        <h3 className="text-lg font-bold text-white">Tracked Position Summary</h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/60 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 rounded-l-lg">Tracked Keyword</th>
                <th className="px-4 py-3">Target Domain</th>
                <th className="px-4 py-3">SERP Rank Position</th>
                <th className="px-4 py-3">Checked Depth</th>
                <th className="px-4 py-3 text-right rounded-r-lg">Data Engine</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {trackedRanks.map((r, idx) => (
                <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-3.5 font-bold text-white flex items-center gap-2">
                    <Award className="h-4 w-4 text-emerald-400" />
                    <span>{r.keyword}</span>
                  </td>
                  <td className="px-4 py-3.5 font-mono text-xs text-slate-400">{r.domain}</td>
                  <td className="px-4 py-3.5">
                    <span
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold font-mono ${
                        r.position === 1
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                          : r.position <= 3
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                          : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                      }`}
                    >
                      <TrendingUp className="h-3.5 w-3.5" />
                      #{r.position} {r.position === 1 ? '🥇 TOP 1' : r.position <= 3 ? 'TOP 3' : 'PAGE 1'}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-slate-400 font-mono">{r.checked_results} Results</td>
                  <td className="px-4 py-3.5 text-right font-mono text-xs text-slate-400">{r.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
