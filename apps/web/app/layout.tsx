import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'IQ Terminal',
  description: 'Local IQ web terminal',
};

import React, { Suspense } from 'react';
import { I18nProvider } from '../lib/i18n/context';

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <Suspense fallback={<div style={{ padding: 20 }}>Loading...</div>}>
          <I18nProvider>{children}</I18nProvider>
        </Suspense>
      </body>
    </html>
  );
}
