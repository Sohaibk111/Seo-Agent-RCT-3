import React from 'react';
import {
  BarChart3,
  Globe,
  Search,
  Sparkles,
  ShieldCheck,
  Mail,
  Zap,
  Activity,
  Sun,
  Moon
} from 'lucide-react';
import { Theme } from '../hooks/useTheme';

export type TabType = 'overview' | 'audit' | 'keywords' | 'metrics' | 'rank' | 'leads' | 'ai';

interface NavbarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  onPrefetchTab?: (tab: TabType) => void;
  auditCount: number;
  theme: Theme;
  toggleTheme: () => void;
}

interface NavItem {
  id: TabType;
  label: string;
  icon: React.ElementType;
  badge?: number;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, onPrefetchTab, auditCount, theme, toggleTheme }) => {
  const navItems: NavItem[] = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'audit', label: 'Technical Audit', icon: ShieldCheck, badge: auditCount > 0 ? auditCount : undefined },
    { id: 'keywords', label: 'Keyword Planner', icon: Search },
    { id: 'metrics', label: 'Domain Metrics', icon: Globe },
    { id: 'rank', label: 'Rank Tracker', icon: Zap },
    { id: 'leads', label: 'Leads & Outreach', icon: Mail },
    { id: 'ai', label: 'AI Advisor', icon: Sparkles },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('overview')}>
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-blue-600 to-indigo-600 p-0.5 shadow-lg shadow-cyan-500/10">
              <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Activity className="h-5 w-5 text-cyan-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-white tracking-tight">SEO Agent</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-semibold">
                  v2.4 FASTAPI
                </span>
              </div>
              <p className="text-xs text-slate-400">Technical Audit & Keyword Engine</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id as TabType)}
                  onMouseEnter={() => onPrefetchTab?.(item.id as TabType)}
                  onFocus={() => onPrefetchTab?.(item.id as TabType)}
                  onTouchStart={() => onPrefetchTab?.(item.id as TabType)}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                  {item.badge !== undefined && (
                    <span className="ml-1 text-[11px] px-1.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-mono">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Status Badge */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="font-mono text-emerald-400 font-medium">FastAPI Engine Ready</span>
            </div>
            <button
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              className="h-9 w-9 flex items-center justify-center rounded-lg border border-slate-700/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Nav */}
        <div className="flex md:hidden overflow-x-auto py-2 gap-1 border-t border-slate-800 scrollbar-none">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id as TabType)}
                onMouseEnter={() => onPrefetchTab?.(item.id as TabType)}
                onTouchStart={() => onPrefetchTab?.(item.id as TabType)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap ${
                  isActive ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-400'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
