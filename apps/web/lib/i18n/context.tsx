'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { type Locale, type Dictionary, DICTIONARY, translateKnownLabel, translateKnownValue, probabilityExplanation } from './dictionary';

type I18nContextType = {
  locale: Locale;
  t: Dictionary;
  translateLabel: (value: string) => string;
  translateValue: (value: string) => string;
  explainProbability: (value: string) => string;
};

const I18nContext = createContext<I18nContextType | null>(null);

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const [locale, setLocale] = useState<Locale>('zh');

  useEffect(() => {
    const lang = searchParams.get('lang');
    if (lang === 'en' || lang === 'zh') {
      setLocale(lang);
    }
  }, [searchParams]);

  const value: I18nContextType = {
    locale,
    t: DICTIONARY[locale],
    translateLabel: (val: string) => translateKnownLabel(val, locale),
    translateValue: (val: string) => translateKnownValue(val, locale),
    explainProbability: (val: string) => probabilityExplanation(val, locale),
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
