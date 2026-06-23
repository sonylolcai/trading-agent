'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, BarChart3, History, Terminal } from 'lucide-react';

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

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Primary">
        <div className="rail__brand">
          <Activity size={18} aria-hidden="true" />
          <span>PA</span>
        </div>
        <nav className="rail__nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link key={item.href} className={active ? 'rail__link rail__link--active' : 'rail__link'} href={item.href}>
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
            <p className="eyebrow">PA Agent</p>
            <h1>{title}</h1>
          </div>
          <div className="workspace__meta">Local API: 127.0.0.1:8765</div>
        </header>
        {children}
      </main>
    </div>
  );
}
