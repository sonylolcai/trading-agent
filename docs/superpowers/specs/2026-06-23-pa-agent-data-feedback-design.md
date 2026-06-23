# PA Agent 数据闭环升级设计

## 背景

PA Agent 当前的优势是清晰的价格行为交易流水线：阶段一诊断市场结构，阶段二生成交易决策，程序用确定性规则补充关键节点，并用交易者方程校验入场、止损、止盈和胜率。这套结构适合作为主观交易者的交易副驾驶。

现有短板不在于两阶段架构本身，而在于缺少结果闭环：`estimated_win_rate` 主要来自模型判断，经验库没有系统区分赢家和输家，用户无法用数据确认某类 setup 是否真的有效。因此本次升级目标是把系统从“规则 + LLM 判断”推进到“规则 + LLM 判断 + 历史统计校准”。

## 保留优势

- 保留两阶段流水线：市场诊断 -> 策略路由 -> 交易决策。
- 保留二元决策树闸门：数据不足、看不懂、极端混乱时不交易。
- 保留程序规则与 LLM 分工：程序负责硬校验和一致性，LLM 负责结构解释与上下文推理。
- 保留交易者方程：只有三价、胜率、风险回报都成立时才给出交易机会。
- 保留“不连接券商、不自动下单”的安全边界。

## 目标

1. 增加可复盘的回测与结果统计，让交易逻辑可验证。
2. 用历史 setup 统计校准 `estimated_win_rate`，减少 LLM 主观拍数。
3. 改造经验库，让 LLM 同时看到同类赢家和输家及其结局。
4. 增加模拟盘/信号解锁机制，降低用户直接跟单风险。
5. 最小侵入地增加成交量和股票估值快照，作为辅助过滤，不破坏价格行为主链路。

## 非目标

- 不重写为自动交易系统。
- 不把 PA Agent 改成完整基本面投研平台。
- 不在第一阶段引入多模态截图识别。
- 不让基本面估值强行覆盖短线 K 线入场信号。
- 不改变现有 Al Brooks 价格行为体系、两阶段分析和决策立场分级。

## 方案总览

升级按 P0 -> P1 -> P2 -> P3 推进。

| 优先级 | 模块 | 目的 |
|---|---|---|
| P0 | 回测引擎 | 统计某类 setup 是否真实有效 |
| P0 | setup 胜率统计表 | 校准 `estimated_win_rate` |
| P1 | 经验库质量控制 | 给 LLM 提供带结果的赢家/输家案例 |
| P1 | 模拟盘/信号解锁 | 在统计表现不足前降低实盘误用风险 |
| P2 | 成交量字段 | 辅助突破与衰竭判断 |
| P2 | 股票估值快照 | 股票标的增加估值/质量过滤 |
| P3 | 宏观事件过滤 | 对黄金、外汇、指数等增加事件风险提示 |

## P0：回测引擎

新增包：

```text
pa_agent/backtest/
  __init__.py
  engine.py
  simulator.py
  metrics.py
  reporter.py
  setup_key.py
  stats_store.py
```

### 回测模式

第一版支持两种模式。

`record replay`：
复用 `records/pending` 或用户指定目录中的历史分析记录，读取当时的阶段一诊断、阶段二决策和后续 K 线表现，快速统计已有策略表现。该模式成本低，优先实现。

`llm replay`：
用户指定历史 K 线区间，系统逐根推进并模拟当时只能看到的已收盘 K 线。每个窗口调用现有 TwoStageOrchestrator。为控制成本，必须按 `symbol + timeframe + frame_hash + prompt_hash + settings_hash` 缓存结果。

### 成交模拟

当阶段二输出 `限价单`、`突破单`、`市价单` 时，`simulator.py` 用后续 K 线模拟：

- 是否触发入场。
- 入场后先触发止损还是止盈。
- 若同一根 K 线同时触及止损和止盈，默认按保守规则判止损，并在报告中标记为 ambiguous。
- 统计结果统一转为 R 值：止损为 `-1R`，止盈按实际 reward/risk 计算。
- 未触发订单按 `not_triggered` 记录，不计入已成交胜率，但计入信号质量统计。

### 输出指标

`metrics.py` 输出：

- 总信号数、已触发交易数、未触发数。
- 胜率、平均 R、期望 R、平均盈亏比。
- 最大回撤、连续亏损次数、简化夏普比率。
- 按 `cycle_position`、`direction`、`detected_patterns`、`order_type`、`entry_setup_type`、`decision_stance` 分组的胜率和期望。

## P0：setup 胜率统计表

新增 `setup_key.py` 定义稳定 setup key。

第一版 key：

```text
symbol_class
timeframe_bucket
cycle_position
direction
entry_setup_type
order_type
primary_patterns
decision_stance
```

`stats_store.py` 保存聚合统计，格式优先使用 JSONL 或 SQLite。为避免一次性引入数据库复杂度，第一版可用 JSONL 事件日志 + 派生聚合缓存。

### 胜率校准字段

阶段二决策新增可选字段：

```json
{
  "estimated_win_rate_basis": "historical|hybrid|llm_judgment",
  "historical_win_rate_for_this_setup": 52.3,
  "historical_sample_count": 47,
  "historical_expectancy_r": 0.18
}
```

### 权重规则

- 样本数 `< 20`：保留 LLM 判断，`estimated_win_rate_basis=llm_judgment`。
- 样本数 `20-100`：历史统计与 LLM 判断混合，`estimated_win_rate_basis=hybrid`。
- 样本数 `> 100`：历史统计为主，LLM 只做结构微调，`estimated_win_rate_basis=historical`。

历史胜率必须做平滑，避免小样本极端值误导。第一版使用简单先验：默认先验胜率 50%，先验样本数 20。

## P1：经验库质量控制

现有经验库按 `cycle_position` 取相似案例。升级后，经验条目需要带结果标签：

```text
[经验 #1] 2024-03-15 BTCUSD 1H | 宽通道做多 | 结果: +1.2R
[经验 #2] 2024-03-18 BTCUSD 1H | 宽通道做多 | 结果: -1.0R | 止损触发
[经验 #3] 2024-03-22 BTCUSD 1H | 宽通道做多 | 结果: not_triggered
```

抽样策略：

- 优先加载同 setup key 或相邻 setup key。
- 同时包含赢家和输家。
- 保留完整止损亏损案例，不用 `min_profit_ratio=-0.5` 过滤掉坏经验。
- 跳过没有后续结果的 wait 案例，除非用户明确启用“等待案例参考”。

经验库接口扩展：

```python
read_for_stage2(
    cycle_position,
    direction,
    patterns,
    setup_key=None,
    max_entries=3,
    require_outcome=True,
    include_winners=True,
    include_losers=True,
)
```

## P1：模拟盘/信号解锁

由于 PA Agent 不自动下单，第一版不做“实盘锁”。改为“信号解锁”：

- 未达标时仍可分析。
- 未达标时不弹出高置信交易机会提醒。
- 未达标时不发送飞书/PushPlus 交易机会推送。
- 决策面板明确标记“仅模拟验证，不建议实盘参考”。

配置字段：

```json
{
  "paper_trading_required": true,
  "paper_trading_min_trades": 50,
  "paper_trading_min_win_rate": 40,
  "paper_trading_min_expectancy_r": 0.0,
  "paper_trading_reset_on_symbol_change": true,
  "paper_trading_symbol_min_trades": 20
}
```

解锁按 `symbol_class + timeframe_bucket + decision_stance` 统计，不要求每个具体品种从零开始，但切换到新资产类别时需要重新积累样本。

## P2：成交量字段

在 `KlineBar` 中增加可选 `volume` 字段，默认 `0.0`。各数据源尽量填充：

- A 股、期货、股票：真实成交量。
- 外汇、CFD、部分黄金数据：可能是 tick volume 或数据源内部量，必须标记来源可信度。

Prompt 增加约束：

```text
成交量只用于辅助确认突破有效性和识别衰竭。不得使用 OBV、VWAP 等成交量指标，不得让成交量覆盖价格行为主判断。
```

校验层不把成交量作为硬闸门。

## P2：股票估值快照

新增 `pa_agent/valuation/`：

```text
pa_agent/valuation/
  __init__.py
  snapshot.py
  scoring.py
  schemas.py
```

只对股票标的启用。第一版复用现有东方财富扩展数据中的 PE/PB、市值、财务、行业、机构预测等字段，不为外汇、黄金、加密货币强行估值。

输出：

```json
{
  "valuation_snapshot": {
    "asset_applicability": "stock_only",
    "valuation_level": "cheap|fair|expensive|unknown",
    "quality_score": 0,
    "growth_score": 0,
    "valuation_score": 0,
    "risk_flags": [],
    "verdict": "investable|watch_only|avoid|unknown",
    "reasoning": ""
  }
}
```

融合规则：

- 中长线问题中，估值快照权重更高。
- 短线交易中，估值快照只影响风险提示和仓位倾向，不直接覆盖信号棒、止损、止盈和交易者方程。
- `expensive` 不强制禁止做多；只提示“短线交易，不输出投资价值结论”。
- `cheap` 不允许无信号追多；仍需通过阶段二交易评估。

## P3：宏观事件过滤

新增事件风险层，优先服务黄金、外汇、指数、利率敏感资产。

第一版只做手动或轻量数据源输入：

- 重大事件时间。
- 事件类别。
- 影响资产类别。
- 风险窗口，例如事件前后 2 小时。

命中风险窗口时：

- 在 `risk_assessment` 和 `watch_points` 中注入事件风险。
- 降低突破/均值回归信号置信度。
- 不默认强制不下单，除非用户启用严格事件保护。

## 数据流

```text
K线数据
  -> 阶段一诊断
  -> 程序注入方向、Always In、惯性等规则节点
  -> 策略路由
  -> setup 统计查询
  -> 带历史统计和经验结局的阶段二 prompt
  -> 阶段二交易决策
  -> 程序校验交易者方程
  -> 保存记录
  -> 后续 K 线结局归因
  -> 更新 setup 统计表和经验库结果标签
```

股票标的额外并行：

```text
股票代码
  -> valuation_snapshot
  -> 注入阶段二风险提示
  -> 决策面板展示
```

## UI 影响

新增或调整：

- 决策面板增加“历史统计”区块：样本数、历史胜率、历史期望 R、胜率来源。
- 决策面板增加“模拟验证状态”：已完成样本数、是否解锁提醒。
- 调试页增加 setup key 和统计查询结果。
- 股票标的增加“价值快照”区块。
- 回测报告可先输出为 markdown/JSON 文件，后续再做 GUI。

## 错误处理

- 没有历史统计时，系统回退到原 LLM 判断，并明确标注 basis。
- 回测中 API 失败时记录失败窗口，不中断整个回测。
- 回测中同一根 K 线同时触发止盈止损时按保守止损处理，并标记 ambiguous。
- 估值数据缺失时输出 `valuation_level=unknown`，不得阻断原交易流程。
- volume 缺失或不可信时不参与判断。

## 测试计划

自动化测试：

- setup key 稳定性测试。
- 交易模拟器测试：限价触发、突破触发、市价入场、止损、止盈、同棒冲突。
- 指标计算测试：胜率、期望 R、最大回撤、分组统计。
- 胜率平滑测试：小样本不会产生极端胜率。
- stage2 schema/normalizer 测试：新增胜率来源字段向后兼容。
- 经验库抽样测试：赢家和输家均可被选中。
- 股票估值快照测试：股票启用，非股票跳过。

手动验证：

- 用已有 records 跑 record replay，确认报告可生成。
- 用小窗口跑 llm replay，确认缓存生效。
- 人工构造一笔同棒止盈止损案例，确认保守处理。
- 对 A 股标的确认估值快照显示；对黄金/外汇确认估值层跳过。

## 实施顺序

1. P0-A：实现 setup key、交易模拟器、基础 metrics。
2. P0-B：实现 record replay 报告。
3. P0-C：实现 stats store，并在阶段二注入历史统计。
4. P0-D：扩展 schema/normalizer/决策面板展示胜率来源。
5. P1-A：给经验记录补 outcome 标签并改造抽样。
6. P1-B：实现模拟验证状态和提醒解锁。
7. P2-A：增加 volume 字段和 prompt 辅助规则。
8. P2-B：增加股票估值快照。
9. P3：增加宏观事件过滤。

## 待用户确认

本设计建议先实现 P0 和 P1，暂缓多模态截图识别。若后续确实需要视觉辅助，应在历史统计闭环完成后，再评估它是否带来可量化收益。
