'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Activity, BarChart3, History, Terminal, Languages } from 'lucide-react';
import { useI18n } from '../lib/i18n/context';

const navItems = [
  { href: '/terminal', label: 'Terminal', icon: Terminal },
  { href: '/history', label: 'History', icon: History },
  { href: '/backtest', label: 'Backtest', icon: BarChart3 },
];

type AppShellProps = {
  title: string;
  children: React.ReactNode;
};

export function AppShell({ title, children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { locale } = useI18n();

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
          <Activity size={18} aria-hidden="true" />
          <span>IQ</span>
        </div>
        <nav className="rail__nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link key={item.href} className={active ? 'rail__link rail__link--active' : 'rail__link'} href={`${item.href}?lang=${locale}`}>
                <Icon size={16} aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="workspace">
        <header className="workspace__header">
          <div>
            <p className="eyebrow">IQ</p>
            <h1>{title}</h1>
          </div>
          <div className="workspace__meta" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button className="icon-button" style={{ height: 'auto', padding: '4px 8px' }} type="button" onClick={toggleLanguage} aria-label="Toggle Language">
              <Languages size={15} aria-hidden="true" />
              <span>{locale === 'zh' ? 'EN' : '中文'}</span>
            </button>
            <span>Local API: 127.0.0.1:8765</span>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
