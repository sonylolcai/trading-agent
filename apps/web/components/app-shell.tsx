'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Activity, BarChart3, Clock, Coins, History, Languages, Radio, Terminal, Zap } from 'lucide-react';
import { useI18n } from '../lib/i18n/context';

type AppShellProps = {
  title: string;
  children: React.ReactNode;
};

export function AppShell({ title, children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { locale, t } = useI18n();
  const [timeUtc, setTimeUtc] = useState('');
  const [timeLocal, setTimeLocal] = useState('');

  const navItems = [
    { href: '/terminal', label: t.navTerminal, icon: Terminal, badge: 'AI STAGE 2', badgeTone: 'cyan' },
    { href: '/live', label: t.navLive, icon: Zap, badge: 'LIVE', badgeTone: 'green', isPulse: true },
    { href: '/crypto', label: t.navCrypto, icon: Coins, badge: 'OKX LAB', badgeTone: 'amber' },
    { href: '/history', label: t.navHistory, icon: History, badge: 'AUDIT', badgeTone: 'neutral' },
    { href: '/backtest', label: t.navBacktest, icon: BarChart3, badge: 'PA VOL', badgeTone: 'purple' },
  ];

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeUtc(now.toUTCString().slice(17, 25) + ' UTC');
      setTimeLocal(now.toLocaleTimeString([], { hour12: false }) + ' LOC');
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const toggleLanguage = () => {
    const nextLocale = locale === 'zh' ? 'en' : 'zh';
    const params = new URLSearchParams(searchParams);
    params.set('lang', nextLocale);
    router.push(`${pathname}?${params.toString()}`);
  };

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Primary">
        <div className="rail__brand">
          <div className="rail__brand-icon">
            <Activity size={18} aria-hidden="true" />
          </div>
          <div className="rail__brand-text">
            <span className="rail__brand-name">PA QUANT</span>
            <span className="rail__brand-tag">ENGINE v2.4</span>
          </div>
        </div>
        <nav className="rail__nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                className={active ? 'rail__link rail__link--active' : 'rail__link'}
                href={`${item.href}?lang=${locale}`}
              >
                <div className="rail__link-main">
                  <Icon size={16} aria-hidden="true" />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className={`rail__link-badge rail__link-badge--${item.badgeTone}`}>
                    {item.isPulse && <span className="rail__pulse-dot" />}
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="rail__footer">
          <div className="rail__telemetry-chip">
            <Radio size={12} className="pulse-icon text-emerald" />
            <span>{t.coreNode}</span>
          </div>
        </div>
      </aside>
      <main className="workspace">
        <header className="workspace__header">
          <div className="workspace__header-left">
            <div className="workspace__eyebrow-row">
              <p className="eyebrow">{t.brandSubtitle}</p>
              <span className="workspace__version-tag">STABLE</span>
            </div>
            <h1>{title}</h1>
          </div>
          <div className="workspace__meta">
            {timeUtc && (
              <div className="workspace__clock-pill" title={t.worldFinancialTime}>
                <Clock size={13} aria-hidden="true" />
                <span className="workspace__clock-val">{timeUtc}</span>
                <span className="workspace__clock-divider">|</span>
                <span className="workspace__clock-sub">{timeLocal}</span>
              </div>
            )}
            <div className="workspace__status-pill">
              <span className="workspace__status-dot" />
              <span className="workspace__status-text">127.0.0.1:8765</span>
              <span className="workspace__status-ping">12ms</span>
            </div>
            <button
              className="workspace__lang-toggle"
              type="button"
              onClick={toggleLanguage}
              aria-label="Toggle Language"
            >
              <Languages size={14} aria-hidden="true" />
              <span>{locale === 'zh' ? 'EN' : '中文'}</span>
            </button>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

