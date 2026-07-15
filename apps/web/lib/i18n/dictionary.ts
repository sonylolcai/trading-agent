export type Locale = 'zh' | 'en';

export type Dictionary = {
  language: string;
  chinese: string;
  english: string;
  empty: string;
  structuredReport: string;
  decisionTree: string;
  decisionPath: string;
  klineFlow: string;
  probabilityForecast: string;
  keyFactors: string;
  trace: string;
  observations: string;
  forecast: string;
  nodes: string;
  bars: string;
  probability: string;
  node: string;
  question: string;
  answer: string;
  basis: string;
  reason: string;
  terminal: string;
  step: string;
  phase: string;
  // Terminal labels
  source: string;
  symbol: string;
  timeframe: string;
  riskProfile: string;
  signalThreshold: string;
  apply: string;
  fetchData: string;
  refresh: string;
  loading: string;
  analyze: string;
  cancel: string;
  analysisStream: string;
  analysisReport: string;
  klineSnapshot: string;
  collapse: string;
  expand: string;
};

export const DICTIONARY: Record<Locale, Dictionary> = {
  zh: {
    language: '语言',
    chinese: '中文',
    english: 'EN',
    empty: '暂无分析报告。',
    structuredReport: '结构化分析报告',
    decisionTree: '决策树可视化',
    decisionPath: '决策路径',
    klineFlow: '逐K线流程',
    probabilityForecast: '概率预测',
    keyFactors: '关键因素',
    trace: '路径',
    observations: '观察项',
    forecast: '预测',
    nodes: '节点',
    bars: 'K线',
    probability: '概率',
    node: '节点',
    question: '问题',
    answer: '回答',
    basis: '依据',
    reason: '理由',
    terminal: '终点',
    step: '步骤',
    phase: '阶段',
    source: '数据源',
    symbol: '标的',
    timeframe: '周期',
    riskProfile: '风险档位',
    signalThreshold: '信号门槛',
    apply: '应用',
    fetchData: '获取数据',
    refresh: '刷新',
    loading: '加载中',
    analyze: '分析',
    cancel: '取消',
    analysisStream: '分析流',
    analysisReport: '分析报告',
    klineSnapshot: 'K线快照',
    collapse: '收起',
    expand: '展开',
  },
  en: {
    language: 'Language',
    chinese: '中文',
    english: 'EN',
    empty: 'No analysis report returned yet.',
    structuredReport: 'Structured analysis report',
    decisionTree: 'Decision Tree',
    decisionPath: 'Decision Path',
    klineFlow: 'K-line Flow',
    probabilityForecast: 'Probability Forecast',
    keyFactors: 'Key Factors',
    trace: 'trace',
    observations: 'observations',
    forecast: 'forecast',
    nodes: 'nodes',
    bars: 'bars',
    probability: 'probability',
    node: 'Node',
    question: 'Question',
    answer: 'Answer',
    basis: 'Basis',
    reason: 'Reason',
    terminal: 'Terminal',
    step: 'Step',
    phase: 'Phase',
    source: 'Source',
    symbol: 'Symbol',
    timeframe: 'Timeframe',
    riskProfile: 'Risk Profile',
    signalThreshold: 'Signal Threshold',
    apply: 'Apply',
    fetchData: 'Fetch Data',
    refresh: 'Refresh',
    loading: 'Loading',
    analyze: 'Analyze',
    cancel: 'Cancel',
    analysisStream: 'Analysis Stream',
    analysisReport: 'Analysis Report',
    klineSnapshot: 'K-line Snapshot',
    collapse: 'Collapse',
    expand: 'Expand',
  },
};

type Term = {
  zh: string;
  en: string;
  zhDescription?: string;
  enDescription?: string;
  aliases: string[];
};

const TERMS: Term[] = [
  { zh: '风险档位', en: 'Risk profile', aliases: ['risk profile', 'risk_profile', '风险档位'] },
  { zh: '信号门槛', en: 'Signal threshold', aliases: ['signal threshold', 'signal_threshold', '信号门槛'] },
  { zh: '稳健', en: 'Conservative', aliases: ['conservative', '稳健'] },
  { zh: '均衡', en: 'Balanced', aliases: ['balanced', '均衡'] },
  { zh: '进取', en: 'Aggressive', aliases: ['aggressive', '进取'] },
  { zh: '强进取', en: 'Extreme aggressive', aliases: ['extreme_aggressive', 'extreme aggressive', '强进取'] },
  { zh: '交易信心', en: 'Trade confidence', aliases: ['trade confidence', '交易信心'] },
  { zh: '诊断信心', en: 'Diagnosis confidence', aliases: ['diagnosis confidence', '诊断信心'] },
  { zh: '预估胜率', en: 'Win rate', aliases: ['win rate', 'estimated win rate', '预估胜率', '估计胜率'] },
  { zh: '历史胜率', en: 'Historical win rate', aliases: ['historical win rate', '历史胜率'] },
  { zh: '样本数', en: 'Samples', aliases: ['samples', 'sample count', 'historical samples', '历史样本', '样本数'] },
  { zh: '历史期望R', en: 'Expectancy R', aliases: ['expectancy r', 'historical expectancy r', '历史期望r'] },
  { zh: '订单类型', en: 'Order type', aliases: ['order type', '订单类型'] },
  { zh: '入场价', en: 'Entry', aliases: ['entry', 'entry price', '入场价'] },
  { zh: '止损价', en: 'Stop loss', aliases: ['stop loss', 'stop loss price', '止损价'] },
  { zh: '止盈价', en: 'Take profit', aliases: ['take profit', 'take profit price', '止盈价'] },
  { zh: '终点', en: 'Terminal', aliases: ['terminal', '终点'] },
  { zh: '阶段一闸门判断', en: 'Diagnostic gate', aliases: ['diagnostic gate', 'stage 1 gate', '阶段一闸门判断'] },
  { zh: '阶段二决策路径', en: 'Decision trace', aliases: ['decision trace', 'stage 2 decision path', '阶段二决策路径'] },
  { zh: '逐K线结构流程', en: 'Bar-by-bar flow', aliases: ['bar-by-bar flow', 'bar flow', '逐k线结构流程'] },
  { zh: '关键因素', en: 'Key factors', aliases: ['key factors', '关键因素'] },
  { zh: '观察点', en: 'Watch points', aliases: ['watch points', '观察点'] },
  { zh: '观察到的信号', en: 'Observed signals', aliases: ['observed signals', '观察到的信号'] },
  { zh: '下一根K线预测', en: 'Next bar prediction', aliases: ['next bar', 'next bar prediction', '下一根k线预测'] },
  { zh: '下一周期预测', en: 'Next cycle prediction', aliases: ['next cycle prediction', '下一周期预测'] },
  { zh: '做多', en: 'Long', aliases: ['long', 'bullish', '做多', '多头'] },
  { zh: '做空', en: 'Short', aliases: ['short', 'bearish', '做空', '空头'] },
  { zh: '中性', en: 'Neutral', aliases: ['neutral', '中性'] },
  { zh: '不下单', en: 'No order', aliases: ['no order', 'wait', 'hold', '不下单', '等待'] },
  { zh: '市价单', en: 'Market', aliases: ['market', 'market order', '市价单'] },
  { zh: '限价单', en: 'Limit', aliases: ['limit', 'limit order', '限价单'] },
  { zh: '突破单', en: 'Breakout', aliases: ['breakout', 'breakout order', '突破单'] },
  {
    zh: '正常通道',
    en: 'Normal channel',
    aliases: ['normal_channel', 'normal channel', '正常通道'],
    zhDescription: '趋势通道仍然清晰，价格更可能沿通道继续推进。',
    enDescription: 'The trend channel is still readable, so price is more likely to keep moving inside the channel.',
  },
  {
    zh: '交易区间',
    en: 'Trading range',
    aliases: ['trading_range', 'trading range', '交易区间'],
    zhDescription: '多空暂时均衡，价格更可能在上下边界之间来回测试。',
    enDescription: 'Buyers and sellers are balanced, so price is more likely to rotate between range boundaries.',
  },
  {
    zh: '极端震荡',
    en: 'Extreme range',
    aliases: ['extreme_tr', 'extreme trading range', '极端震荡'],
    zhDescription: '结构噪声很高，方向预测可信度较低。',
    enDescription: 'Market noise is high, so directional forecasts are less reliable.',
  },
  {
    zh: '偏多',
    en: 'Bullish',
    aliases: ['bullish', 'bull', '偏多'],
    zhDescription: '下一阶段更偏向上涨延续。',
    enDescription: 'The next phase leans toward bullish continuation.',
  },
  {
    zh: '偏空',
    en: 'Bearish',
    aliases: ['bearish', 'bear', '偏空'],
    zhDescription: '下一阶段更偏向下跌延续。',
    enDescription: 'The next phase leans toward bearish continuation.',
  },
];

const TERM_INDEX = new Map<string, Term>();

for (const term of TERMS) {
  for (const alias of term.aliases) {
    TERM_INDEX.set(normalize(alias), term);
  }
}

function normalize(value: string): string {
  return value.trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function findTerm(value: string): Term | undefined {
  return TERM_INDEX.get(normalize(value));
}

export function translateKnownLabel(value: string, locale: Locale): string {
  return findTerm(value)?.[locale] ?? value;
}

export function translateKnownValue(value: string, locale: Locale): string {
  return translateKnownLabel(value, locale);
}

export function probabilityExplanation(value: string, locale: Locale): string {
  const term = findTerm(value);
  if (!term) {
    return '';
  }
  return locale === 'zh' ? term.zhDescription ?? '' : term.enDescription ?? '';
}
