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
  liveStream: string;
  tickerMatrix: string;
  orderBook: string;
  tradeTape: string;
  throughput: string;
  latency: string;
  whaleAlert: string;

  // Nav items & shell
  navTerminal: string;
  navLive: string;
  navCrypto: string;
  navHistory: string;
  navBacktest: string;
  brandSubtitle: string;
  coreNode: string;
  worldFinancialTime: string;
  quickPresets: string;
  copy: string;
  copied: string;
  noCachedKline: string;

  // Rolling backtest
  rollingBacktestTitle: string;
  rollingBacktestWarming: string;
  evaluatedWindows: string;
  tradeSignals: string;
  completedTrades: string;
  winRate: string;
  expectancyR: string;
  totalR: string;
  maxDrawdown: string;
  profitFactor: string;
  rollingEmpty: string;
  thDirection: string;
  thOrder: string;
  thEntry: string;
  thStopLoss: string;
  thTakeProfit: string;
  thStatus: string;
  thRPnL: string;
  thBarsHeld: string;

  // History Page
  historyTitle: string;
  historySub: string;
  historySearchPlaceholder: string;
  historyAll: string;
  historyEmpty: string;
  historyNoMatch: string;
  historyThreshold: string;
  historyFullReport: string;

  // Backtest Page
  backtestTitle: string;
  backtestSub: string;
  rebuild: string;
  rebuilding: string;
  totalSamples: string;
  uniqueSetups: string;
  aggregateWinRate: string;
  winsLosses: string;
  cumulativeTotalR: string;
  acrossAllSetups: string;
  weightedExpectancy: string;
  avgPerTrade: string;
  searchSetupPlaceholder: string;
  showingSetups: string;
  setupsCount: string;
  priceVsVolume: string;
  priceVsVolumeSub: string;
  volumeConfirmedTitle: string;
  volumeConfirmedDesc: string;
  timeExitTitle: string;
  timeExitDesc: string;
  volumeAuditTitle: string;
  volumeAuditDesc: string;
  metricLabel: string;
  priceOnly: string;
  volumeAssisted: string;
  deltaLabel: string;
  confirmedOnly: string;
  confirmedFixed: string;
  confirmedTime: string;
  contextLabel: string;
  signalsLabel: string;
  completedLabel: string;

  // Live stream & components
  bidDepth: string;
  askDepth: string;
  spread: string;
  cumDepth: string;
  buyFlow: string;
  sellFlow: string;
  amountBuckets: string;
  whaleTrades: string;
  h24Volume: string;
  h24Change: string;
  runtimeHud: string;
  mainThreadFps: string;
  eventLoopDrill: string;
  jsHeap: string;
  dropFrameRate: string;
  drilldownIntraday: string;
  returnToMacro: string;
  presetAll: string;
  preset3M: string;
  preset1M: string;
  preset7D: string;
  geekHotkeys: string;
  hotkeyTimeframe: string;
  hotkeyPauseResume: string;
  hotkeyTimeBrush: string;
  hotkeyCopyPrice: string;
  spaceKey: string;
  dragTimeline: string;
  clickOrderPrice: string;
  activeSymbol: string;
  dataSource: string;
  throttleRate: string;
  whaleThresholdLabel: string;
  searchSymbol: string;
  clickToSwitch: string;
  trendColumn: string;
  volumeColumn: string;
  priceRangeColumn: string;
  change24hColumn: string;
  symbolColumn: string;
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
    liveStream: '实时盘口',
    tickerMatrix: '全币种行情矩阵',
    orderBook: 'L2 深度订单簿',
    tradeTape: '逐笔成交流水',
    throughput: '吞吐率',
    latency: '延迟',
    whaleAlert: '大单警报',

    // Nav & Shell
    navTerminal: '量化终端',
    navLive: '实时盘口',
    navCrypto: '加密实验室',
    navHistory: '历史审计',
    navBacktest: '策略回测',
    brandSubtitle: 'PA 量化引擎',
    coreNode: '核心节点 01',
    worldFinancialTime: '全球金融时区',
    quickPresets: '快速标的预设',
    copy: '复制',
    copied: '已复制',
    noCachedKline: '暂无缓存 K 线数据。',

    // Rolling Backtest
    rollingBacktestTitle: '100根K线滚动回测',
    rollingBacktestWarming: '滚动回测 API 正在预热',
    evaluatedWindows: '评估窗口数',
    tradeSignals: '交易信号',
    completedTrades: '完成交易',
    winRate: '胜率',
    expectancyR: '期望R',
    totalR: '总R',
    maxDrawdown: '最大回撤',
    profitFactor: '盈亏比',
    rollingEmpty: '当前窗口未触发可执行交易；可能是策略等待确认，或没有低风险入场点。',
    thDirection: '方向',
    thOrder: '订单',
    thEntry: '入场',
    thStopLoss: '止损',
    thTakeProfit: '止盈',
    thStatus: '状态',
    thRPnL: 'R 盈亏',
    thBarsHeld: '持仓K数',

    // History Page
    historyTitle: '分析审计记录',
    historySub: '条本地待处理账本记录',
    historySearchPlaceholder: '按标的或动作搜索 (如 000001, BTC)...',
    historyAll: '全部',
    historyEmpty: '暂无分析记录。',
    historyNoMatch: '无匹配的历史记录。',
    historyThreshold: '阈值',
    historyFullReport: '完整分析报告',

    // Backtest Page
    backtestTitle: 'Setup 策略形态统计',
    backtestSub: '组本地账本形态统计',
    rebuild: '重建统计',
    rebuilding: '重建中',
    totalSamples: '总样本覆盖',
    uniqueSetups: '组独立形态',
    aggregateWinRate: '综合胜率',
    winsLosses: '胜 / 负',
    cumulativeTotalR: '累计总收益',
    acrossAllSetups: '全形态历史总和',
    weightedExpectancy: '加权期望收益',
    avgPerTrade: '每笔交易平均期望',
    searchSetupPlaceholder: '搜索 Setup 策略形态 (如 bull_flag, pinbar)...',
    showingSetups: '显示',
    setupsCount: '组',
    priceVsVolume: '价格行为 vs 硬成交量过滤器',
    priceVsVolumeSub: '基于相同缓存K线、风险档位、出入场规则与模拟撮合。',
    volumeConfirmedTitle: '成交量确认候选方案',
    volumeConfirmedDesc: '仅供量化研究：仅当成交量与收盘强度共同确认突破时才保留价格信号。',
    timeExitTitle: '10根K线时间止损基准',
    timeExitDesc: '仅供量化研究基准：采用相同成交量确认入场与初始止损；若10根K线未触及止损止盈，则按收盘价退出。',
    volumeAuditTitle: '成交量环境审计',
    volumeAuditDesc: '所有价格行为信号在此审计统计；环境标签不影响入场、出场与仓位管理。',
    metricLabel: '指标',
    priceOnly: '纯价格',
    volumeAssisted: '成交量辅助',
    deltaLabel: '差值 (Delta)',
    confirmedOnly: '仅确认',
    confirmedFixed: '确认固定出场',
    confirmedTime: '确认时间出场',
    contextLabel: '环境',
    signalsLabel: '信号数',
    completedLabel: '完成数',

    // Live stream & components
    bidDepth: '买盘累计',
    askDepth: '卖盘累计',
    spread: '买卖价差',
    cumDepth: '累计深度',
    buyFlow: '买盘优势',
    sellFlow: '卖盘优势',
    amountBuckets: '金额分箱',
    whaleTrades: '巨鲸大单',
    h24Volume: '24h 成交额',
    h24Change: '24h 涨跌幅',
    runtimeHud: '运行时性能监视器',
    mainThreadFps: '主线程 FPS',
    eventLoopDrill: '事件循环延迟',
    jsHeap: '堆内存占用',
    dropFrameRate: '丢帧率',
    drilldownIntraday: '瞬间下钻单日分时 (15m)',
    returnToMacro: '返回多月宏观 (1D)',
    presetAll: '全部 (All)',
    preset3M: '近3个月 (3M)',
    preset1M: '近1个月 (1M)',
    preset7D: '近7天 (7D)',
    geekHotkeys: '极客快捷操作',
    hotkeyTimeframe: '秒切周期 (1m / 15m / 30m / 1h / 4h / 1D)',
    hotkeyPauseResume: '流推送暂停/继续',
    hotkeyTimeBrush: '宏微时间笔刷下钻',
    hotkeyCopyPrice: '复制委托价格',
    spaceKey: 'Space 空格',
    dragTimeline: '拖拽微缩轴',
    clickOrderPrice: '点击盘口价',
    activeSymbol: '当前标的',
    dataSource: '数据源',
    throttleRate: '渲染采样',
    whaleThresholdLabel: '大单阈值 (U)',
    searchSymbol: '搜索代码...',
    clickToSwitch: '点击切换至',
    trendColumn: '走势',
    volumeColumn: '成交量',
    priceRangeColumn: '最新价 / 24h区间',
    change24hColumn: '24h 涨跌',
    symbolColumn: '标的',
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
    liveStream: 'Live Stream',
    tickerMatrix: 'Ticker Matrix',
    orderBook: 'L2 Order Book',
    tradeTape: 'Trade Tape',
    throughput: 'Throughput',
    latency: 'Latency',
    whaleAlert: 'Whale Alert',

    // Nav & Shell
    navTerminal: 'Terminal',
    navLive: 'Live Stream',
    navCrypto: 'Crypto Lab',
    navHistory: 'History',
    navBacktest: 'Backtest',
    brandSubtitle: 'PA QUANT ENGINE',
    coreNode: 'CORE NODE 01',
    worldFinancialTime: 'World Financial Time',
    quickPresets: 'Quick Presets',
    copy: 'Copy',
    copied: 'Copied',
    noCachedKline: 'No cached K-line frame available.',

    // Rolling Backtest
    rollingBacktestTitle: '100-Bar Rolling Backtest',
    rollingBacktestWarming: 'Rolling backtest API is warming up',
    evaluatedWindows: 'Evaluated Windows',
    tradeSignals: 'Trade Signals',
    completedTrades: 'Completed Trades',
    winRate: 'Win Rate',
    expectancyR: 'Expectancy R',
    totalR: 'Total R',
    maxDrawdown: 'Max Drawdown',
    profitFactor: 'Profit Factor',
    rollingEmpty: 'No executable trades triggered in current window; strategy may be waiting for confirmation or low-risk entry.',
    thDirection: 'Direction',
    thOrder: 'Order',
    thEntry: 'Entry',
    thStopLoss: 'Stop Loss',
    thTakeProfit: 'Take Profit',
    thStatus: 'Status',
    thRPnL: 'R PnL',
    thBarsHeld: 'Bars Held',

    // History Page
    historyTitle: 'Analysis Records',
    historySub: 'records from local pending store',
    historySearchPlaceholder: 'Search symbol or action (e.g. 000001, BTC)...',
    historyAll: 'All',
    historyEmpty: 'No analysis records returned.',
    historyNoMatch: 'No records match the current filter.',
    historyThreshold: 'Threshold',
    historyFullReport: 'Complete Analysis Report',

    // Backtest Page
    backtestTitle: 'Setup Statistics',
    backtestSub: 'setup buckets from local stats ledger',
    rebuild: 'Rebuild',
    rebuilding: 'Rebuilding',
    totalSamples: 'Total Samples',
    uniqueSetups: 'unique setups',
    aggregateWinRate: 'Aggregate Win Rate',
    winsLosses: 'W / L',
    cumulativeTotalR: 'Cumulative Total R',
    acrossAllSetups: 'Across all setups',
    weightedExpectancy: 'Weighted Expectancy',
    avgPerTrade: 'Avg expectancy per trade',
    searchSetupPlaceholder: 'Search setup key (e.g. bull_flag, pinbar)...',
    showingSetups: 'Showing',
    setupsCount: 'setups',
    priceVsVolume: 'Price Action vs Hard Volume Filter',
    priceVsVolumeSub: 'Same cached K-lines, risk profile, entries, stops, targets, and simulator.',
    volumeConfirmedTitle: 'Volume-Confirmed Candidate',
    volumeConfirmedDesc: 'Research-only: keeps price signals only when volume and closing strength confirm the breakout.',
    timeExitTitle: '10-Bar Time-Exit Benchmark',
    timeExitDesc: 'Research-only benchmark: uses volume-confirmed entries and initial stops; if neither stop nor target is hit, exits at bar 10 close.',
    volumeAuditTitle: 'Volume Context Audit',
    volumeAuditDesc: 'Every price-action signal is measured here; these labels do not alter entries, exits, or position size.',
    metricLabel: 'Metric',
    priceOnly: 'Price only',
    volumeAssisted: 'Volume assisted',
    deltaLabel: 'Delta',
    confirmedOnly: 'Confirmed only',
    confirmedFixed: 'Confirmed fixed exit',
    confirmedTime: 'Confirmed time exit',
    contextLabel: 'Context',
    signalsLabel: 'Signals',
    completedLabel: 'Completed',

    // Live stream & components
    bidDepth: 'Bids Depth',
    askDepth: 'Asks Depth',
    spread: 'Spread',
    cumDepth: 'Cumulative Depth',
    buyFlow: 'Buy Flow',
    sellFlow: 'Sell Flow',
    amountBuckets: 'Amount Buckets',
    whaleTrades: 'Whale Trades',
    h24Volume: '24h Volume',
    h24Change: '24h Change',
    runtimeHud: 'Runtime Engine HUD',
    mainThreadFps: 'Main Thread FPS',
    eventLoopDrill: 'Event Loop Drift',
    jsHeap: 'JS Heap Memory',
    dropFrameRate: 'Dropped Frames',
    drilldownIntraday: 'Drilldown Intraday (15m)',
    returnToMacro: 'Return to Macro (1D)',
    presetAll: 'All',
    preset3M: '3M',
    preset1M: '1M',
    preset7D: '7D',
    geekHotkeys: 'Geek Shortcuts',
    hotkeyTimeframe: 'Switch timeframe (1m - 1D)',
    hotkeyPauseResume: 'Pause / resume stream',
    hotkeyTimeBrush: 'Time-range brush drilldown',
    hotkeyCopyPrice: 'Copy order price',
    spaceKey: 'Space',
    dragTimeline: 'Drag timeline',
    clickOrderPrice: 'Click order price',
    activeSymbol: 'Active Symbol',
    dataSource: 'Data Source',
    throttleRate: 'Throttle',
    whaleThresholdLabel: 'Whale Alert (U)',
    searchSymbol: 'Search symbol...',
    clickToSwitch: 'Click to switch to',
    trendColumn: 'Trend',
    volumeColumn: 'Volume',
    priceRangeColumn: 'Last Price / 24h Range',
    change24hColumn: '24h Change',
    symbolColumn: 'Symbol',
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
  { zh: '胜率基准', en: 'Win-rate basis', aliases: ['win-rate basis', 'win_rate_basis', '胜率基准'] },
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
