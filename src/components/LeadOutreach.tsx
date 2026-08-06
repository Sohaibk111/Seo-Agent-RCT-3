import React, { useState } from 'react';
import { Mail, Send, CheckCircle2, User, Globe, Sparkles, Building2 } from 'lucide-react';
import { Lead, Website } from '../types';

interface LeadOutreachProps {
  leads: Lead[];
  websites: Website[];
}

export const LeadOutreach: React.FC<LeadOutreachProps> = ({ leads, websites }) => {
  const [selectedLead, setSelectedLead] = useState<Lead | null>(leads.length > 0 ? leads[0] : null);
  const [toEmail, setToEmail] = useState(selectedLead?.email || 'contact@techflow-seo.com');
  const [subject, setSubject] = useState('Technical SEO Opportunities & Audit Summary for TechFlow');
  const [body, setBody] = useState(
    `Hi Team,\n\nWe recently analyzed your site's technical SEO health and discovered key optimizations around page title length, mobile viewport tags, and image alt text that can increase your search traffic by 25%.\n\nWould you be open to a quick 10-minute overview?\n\nBest regards,\nSEO Growth Team`
  );
  const [isSending, setIsSending] = useState(false);
  const [sendSuccess, setSendSuccess] = useState(false);

  const handleSelectLead = (lead: Lead) => {
    setSelectedLead(lead);
    setToEmail(lead.email);
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!toEmail || !subject || !body) return;

    setIsSending(true);
    setSendSuccess(false);

    try {
      const res = await fetch('/api/v1/outreach/email/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock_jwt_token_sample'
        },
        body: JSON.stringify({ to_email: toEmail, subject, body })
      });
      if (res.ok) {
        setSendSuccess(true);
        setTimeout(() => setSendSuccess(false), 4000);
      }
    } catch (err) {
      console.error('Failed to send outreach email', err);
    } finally {
      setIsSending(false);
    }
  };

  const applyTemplate = (type: 'audit_proposal' | 'quick_fix' | 'partnership') => {
    if (type === 'audit_proposal') {
      setSubject('Free Technical SEO Audit & Traffic Recommendations');
      setBody(
        `Hello,\n\nOur automated audit engine identified 3 critical opportunities to boost your organic reach and fix technical bottlenecks on your site.\n\nLet me know if you'd like the full report PDF!\n\nBest,`
      );
    } else if (type === 'quick_fix') {
      setSubject('Quick SEO Fixes for your Title & Meta Tags');
      setBody(
        `Hi,\n\nWe noticed a few missing alt text tags and unoptimized meta descriptions on your domain. Fixing these quick wins will immediately improve indexation.\n\nCheers,`
      );
    } else {
      setSubject('SEO Partnership & Growth Strategy Proposal');
      setBody(
        `Hi there,\n\nWe help companies scale search visibility with high-intent keyword clustering and automated rank tracking. Let's explore working together.\n\nBest,`
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl">
        <h2 className="text-xl font-bold text-white flex items-center gap-2 mb-1">
          <Mail className="h-6 w-6 text-amber-400" />
          <span>Lead & Contact Outreach Dispatcher</span>
        </h2>
        <p className="text-xs text-slate-400">
          Reach out to domain contacts discovered during site audits with customized proposal templates.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Extracted Leads List */}
        <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
          <h3 className="text-base font-bold text-white flex items-center justify-between">
            <span>Discovered Contacts</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-amber-400 font-mono">
              {leads.length} Contacts
            </span>
          </h3>

          <div className="space-y-2">
            {leads.map((lead) => {
              const site = websites.find((w) => w.id === lead.website_id);
              const isSelected = selectedLead?.id === lead.id;

              return (
                <div
                  key={lead.id}
                  onClick={() => handleSelectLead(lead)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-amber-500/10 border-amber-500/40 text-white'
                      : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <User className="h-4 w-4 text-amber-400 shrink-0" />
                    <span className="font-bold text-sm truncate">{lead.email}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-slate-400 mt-2">
                    <span className="flex items-center gap-1">
                      <Globe className="h-3 w-3" />
                      {site?.domain || 'Target Site'}
                    </span>
                    <span className="font-mono text-[10px] bg-slate-800 px-1.5 py-0.5 rounded">
                      {lead.source}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Email Composer */}
        <div className="lg:col-span-2 bg-slate-900 rounded-2xl border border-slate-800 p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <h3 className="text-lg font-bold text-white">Outreach Email Composer</h3>

            {/* Template Selector */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Templates:</span>
              <button
                onClick={() => applyTemplate('audit_proposal')}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-amber-300 rounded-lg transition-colors"
              >
                Audit Proposal
              </button>
              <button
                onClick={() => applyTemplate('quick_fix')}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-amber-300 rounded-lg transition-colors"
              >
                Quick Fixes
              </button>
            </div>
          </div>

          {sendSuccess && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              <span>Outreach email dispatched successfully to {toEmail}!</span>
            </div>
          )}

          <form onSubmit={handleSend} className="space-y-4 text-sm">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Recipient Email</label>
              <input
                type="email"
                value={toEmail}
                onChange={(e) => setToEmail(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Subject Line</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Message Body</label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={6}
                required
                className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>

            <button
              type="submit"
              disabled={isSending}
              className="w-full py-3 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-black font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20 disabled:opacity-50"
            >
              {isSending ? (
                <div className="h-4 w-4 border-2 border-black border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <Send className="h-4 w-4" />
              )}
              <span>Dispatch Outreach Email</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
