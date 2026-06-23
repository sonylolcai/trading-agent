import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PA Agent Terminal',
  description: 'Local PA Agent web terminal',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
