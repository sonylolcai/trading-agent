import { describe, expect, it } from 'vitest';
import {
  DICTIONARY,
  probabilityExplanation,
  translateKnownLabel,
  translateKnownValue,
} from '../lib/i18n/dictionary';

describe('analysis report i18n', () => {
  it('defaults report copy to Chinese and supports English labels', () => {
    expect(DICTIONARY['zh'].decisionTree).toBe('决策树可视化');
    expect(DICTIONARY['en'].decisionTree).toBe('Decision Tree');
    expect(translateKnownLabel('Trade confidence', 'zh')).toBe('交易信心');
    expect(translateKnownLabel('交易信心', 'en')).toBe('Trade confidence');
  });

  it('explains English next-cycle indicators in Chinese', () => {
    expect(translateKnownLabel('normal_channel', 'zh')).toBe('正常通道');
    expect(translateKnownValue('trading_range', 'zh')).toBe('交易区间');
    expect(probabilityExplanation('normal_channel', 'zh')).toContain('通道');
    expect(probabilityExplanation('normal_channel', 'en')).toContain('channel');
  });
});
