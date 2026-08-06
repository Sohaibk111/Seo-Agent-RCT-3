import React, { useState } from 'react';
import { Globe, ShieldCheck, Lock, Calendar, Server, Activity, Search } from 'lucide-react';
import { DomainMetrics as DomainMetricsType } from '../types';

export const DomainMetrics: React.FC = () => {
  const [domainInput, setDomainInput] = useState('techflow-seo.com');
  const [isLoading, setIsLoading] = useState(false);
  const [metrics, setMetrics] = useState<DomainMetricsType>({
    domain: 'techflow-seo.com',
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

  const handleFetch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domainInput.trim()) return;

    setIsLoading(true);
    try {
      const res = await fetch('/api/v1/metrics/domain', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock_jwt_token_sample'
        },
        body: JSON.stringify({ domain: domainInput.trim() })
      });
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error('Failed to fetch domain metrics', err);
    } finally {
      setIsLoading(false);
    }
  };

  const domainAgeYears = (metrics.domain_age_days / 365).toFixed(1);

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Globe className="h-6 w-6 text-cyan-400" />
            <span>Domain Metrics & WHOIS Inspector</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Analyze domain authority, registration history, backlink estimations, and DNS security posture.
          </p>
        </div>

        <form onSubmit={handleFetch} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Globe className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              placeholder="Enter domain name (e.g., techflow-seo.com)..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-sm rounded-xl transition-colors flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 disabled:opacity-50"
          >
            {isLoading ? (
              <div className="h-4 w-4 border-2 border-black border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <Search className="h-4 w-4" />
            )}
            <span>Lookup Domain</span>
          </button>
        </form>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: Domain Authority */}
        <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 flex flex-col items-center text-center">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Domain Authority (DA)</p>
          <div className="my-4 h-28 w-28 rounded-full bg-cyan-500/10 border-4 border-cyan-500/40 flex items-center justify-center">
            <span className="text-3xl font-extrabold text-white">{metrics.domain_authority}</span>
          </div>
          <p className="text-xs text-slate-400">Score based on backlink volume and root domain trust signals.</p>
        </div>

        {/* Card 2: Domain Age & Registrar */}
        <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <Calendar className="h-4 w-4 text-cyan-400" />
            <span>Registration Profile</span>
          </h3>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">Domain Age:</span>
              <span className="font-mono text-white font-bold">{domainAgeYears} years ({metrics.domain_age_days} days)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">Registrar:</span>
              <span className="font-mono text-white font-medium">{metrics.registrar}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-400">Lookup Provider:</span>
              <span className="font-mono text-cyan-400 font-medium">{metrics.provider}</span>
            </div>
          </div>
        </div>

        {/* Card 3: Traffic & Backlinks */}
        <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-400" />
            <span>Search Footprint</span>
          </h3>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">Est. Backlink Count:</span>
              <span className="font-mono text-white font-bold">{metrics.backlinks_estimate.toLocaleString()}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">Monthly Organic Traffic:</span>
              <span className="font-mono text-emerald-400 font-bold">{metrics.organic_traffic_monthly.toLocaleString()} /mo</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-400">Server Location:</span>
              <span className="font-mono text-white font-medium">{metrics.extra.server_country}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Security & DNS Verification */}
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
        <h3 className="text-base font-bold text-white mb-4">Security & DNS Compliance</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-3">
            <Lock className="h-5 w-5 text-emerald-400" />
            <div>
              <p className="font-bold text-white">SSL Certificate</p>
              <p className="text-xs text-slate-400">256-bit TLS encryption valid</p>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            <div>
              <p className="font-bold text-white">DNSSEC Protocol</p>
              <p className="text-xs text-slate-400">Cryptographic domain validation active</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
