# 需求文档：AI K线分析程序（ai-kline-analyzer）

## 0. 文档说明

本文档采用 EARS 风格，由已批准的 `design.md`（design-first 工作流）反向派生而来。所有条目可独立测试，措辞与设计中的澄清条款 C1–C15 完全一致。EARS 关键字（WHEN / THEN / IF / WHILE / WHERE / SHALL / THE）保留英文以兼容工具，其余使用中文。代码标识符与 JSON 字段名使用英文。

绝对路径基准：`D:\cl\PA_Agent\`。

---

## 1. 引言（Introduction）

本特性是一个运行在 Windows 桌面的**辅助决策工具**，为离散交易者在选定品种与周期上提供基于大语言模型的双阶段 K 线分析。程序持续从 TradingView 拉取 K 线（含未收盘 bar），实时绘图并标注序号；用户点击「提交分析」后，程序按使用说明 v1.0 的两阶段流水线（诊断 → 策略决策）调用 DeepSeek V4 Pro（thinking 模式 + reasoning_effort=max + 1M 上下文窗），输出结构化 JSON 决策；完整记录、AI 推理过程、prompt、原始响应、用量与费用全部本地落盘。程序**不执行任何交易动作**，归类（正题本／错题本）由用户手动完成。

## 2. 用户角色（User Personas）

- **离散交易者（Discretionary Trader，主要用户）**
  - 在选定品种（默认 XAUUSD）与周期（默认 1h）上做手动交易决策；
  - 把本程序当作"第二意见"，结合 AI 输出与自身经验确认是否下单；
  - 自行维护经验库目录，在事后将分析记录手动归类为成功或失败案例；
  - 关心 token 消耗与按百万 token 的成本；
  - 同时是 AI Provider 配置的管理者（model、base URL、API key、thinking、reasoning_effort）。

本特性**仅有一个用户角色**。所有需求都从该角色视角展开。

---

## 3. 需求列表（Requirements）

### 需求 R1：实时 K 线获取与图表绘制

**User Story:** 作为离散交易者，我想要在选定品种与周期下看到一张以 1 秒粒度刷新的 K 线图，且每根 bar 都带可读的序号标注，以便我可以在视觉上对照 AI 输出中的"序号 N"引用。

#### Acceptance Criteria

1. WHEN 程序启动并完成数据源订阅，THE System SHALL 通过 `TradingViewSource` 拉取 K 线数据并填充 `KlineBuffer`。
2. WHILE 数据源已订阅且未被取消，THE System SHALL 每 1000 ms（由 `general.refresh_interval_ms` 控制）触发一次最新快照拉取（C5）。
3. WHEN 用户配置的 bar 数 N 大于等于 2 且缓冲区已就绪，THE System SHALL 在主页 Tab1 的 ChartWidget 上同时绘制全部 N 根 bar（含未收盘 bar）（C8）。
4. THE ChartWidget SHALL 在每根 bar 旁渲染一个序号文本项，序号最大值等于 N，序号最小值等于 1（C9）。
5. THE System SHALL 始终把当前未收盘 bar 标注为 `seq = 1` 且 `closed = False`（C6、C9）。
6. IF 数据源连续 5 秒返回失败或网络异常，THEN THE System SHALL 在主页状态栏显示「数据延迟」文本，且不抛出未捕获异常（设计 §6）。
7. THE System SHALL 不使用使用说明 §12.1 的"30–50 根"显示窗口，而是按用户输入的 N 渲染（C8 覆盖项）。

---

### 需求 R2：可插拔数据源架构

**User Story:** 作为离散交易者，我想要一个解耦的数据源抽象，以便未来切换到 MT5 时不必改动 GUI 与编排层。

#### Acceptance Criteria

1. THE System SHALL 提供 `DataSource` 抽象基类，并至少声明 `connect`、`disconnect`、`list_symbols`、`supported_timeframes`、`subscribe`、`unsubscribe`、`latest_snapshot(n)` 七个方法（设计 §B.2.1）。
2. THE System SHALL 提供 `TradingViewSource` 作为 `DataSource` 的具体实现，且默认启用（C1）。
3. THE System SHALL 提供 `MT5Source` 作为 stub，其方法体允许 `raise NotImplementedError`，但类签名必须实现 `DataSource` 完整接口（C1）。
4. WHEN 编排层、刷新循环、GUI 任意一处需要 K 线数据，THE System SHALL 仅通过 `DataSource` 抽象访问，不直接 import `TradingViewSource` 或 `MT5Source` 的具体实现。
5. WHERE 用户在配置中切换数据源实现，THE System SHALL 在不修改 GUI 与编排层源码的前提下完成替换。

---

### 需求 R3：运行期切换品种与周期

**User Story:** 作为离散交易者，我想要在程序运行中随时切换品种或周期，以便我可以在多个市场上快速调用 AI 助手。

#### Acceptance Criteria

1. WHEN 用户在主页改变 Symbol 或 Timeframe 下拉，THE System SHALL 调用当前 `DataSource.unsubscribe()`，清空 `KlineBuffer`，再以新参数调用 `subscribe(new_symbol, new_timeframe)`（C7、设计 §B.10）。
2. IF 切换发生时存在正在执行的 AI worker，THEN THE System SHALL 通过 `cancel_token.set()` 取消该 worker，并在 5 秒内尝试 join；超时则标记为 zombie 但不强杀（设计 §B.10）。
3. WHEN 因切换导致 AI worker 被取消，THE System SHALL 不增加 `ExceptionCounter.consecutive_count`（C10、设计 §B.14）。
4. WHEN 切换完成，THE System SHALL 重置 ChartWidget 的序号渲染并清空 `FreeChatSession`，使 Tab2 输入框置灰直到下次两阶段成功完成。
5. WHEN 切换被取消的分析 worker 已停止，THE System SHALL 通过 `PendingWriter.save_partial(reason="user_switched")` 落盘部分记录，且 `exception` 字段为 null。

---

### 需求 R4：AI Provider 配置面板与持久化

**User Story:** 作为离散交易者，我想要在 GUI 中编辑 AI 提供方设置并安全持久化，以便我可以更换 API key、调整 thinking / reasoning_effort 而无需改代码。

#### Acceptance Criteria

1. THE GUI SHALL 提供 `SettingsDialog`，且字段包含：`model`、`base_url`、`api_key`、`thinking`（布尔）、`reasoning_effort`（枚举 `low|medium|high|max`）、`context_window`（整数，默认 1_000_000）、`pricing.input_cache_hit`、`pricing.input_cache_miss`、`pricing.output`（C2、C3）。
2. THE Default `AIProviderSettings` SHALL 等于：`model="deepseek-v4-pro"`，`base_url="https://api.deepseek.com"`，`thinking=True`，`reasoning_effort="max"`，`context_window=1_000_000`（C2）。
3. WHEN 用户点击保存，THE System SHALL 把配置写入 `D:\cl\PA_Agent\config\settings.json`，且 `api_key` 字段以 Windows DPAPI 加密后的密文保存为 `api_key_encrypted`（设计 §B.12）。
4. THE `SettingsDialog` 中的 API key 输入框 SHALL 默认采用密码模式（不可见），仅在用户主动点击「显示」时明文回显，且明文回显不会触发持久化。
5. WHEN 任何调试视图、日志或记录文件（含 `meta.ai_provider`）需要展示 API key，THE System SHALL 仅展示 `mask_secret(key) = "****" + key[-4:]` 形式（C3、设计 §B.12）。
6. WHEN 程序下次启动，THE System SHALL 从 `settings.json` 解密读取 API key 并装配到 `DeepSeekClient`，无需用户再次输入。

---

### 需求 R5：双阶段分析流程与 Prompt 拼装

**User Story:** 作为离散交易者，我想要程序按使用说明的两阶段架构组织 prompt 并解析 JSON，以便 AI 的诊断与决策可追溯且可被工具消费。

#### Acceptance Criteria

1. WHEN 用户点击「提交分析」，THE System SHALL 先执行阶段一（诊断），其 system prompt 按以下顺序拼接：`提示词大纲_人设与思维方式.txt`、`市场诊断框架.txt`、`文件16-K线信号识别.txt`（设计 §B.3）。
2. THE 阶段一 user prompt SHALL 至少包含：当前 symbol 与 timeframe、N 根 K 线表（含序号、OHLC、volume）、EMA20 与 ATR14 的对齐序列、用户输入的 HTF 文本、严格 JSON 输出要求（设计 §B.3）。
3. THE 阶段一 AI 响应 SHALL 通过 `JsonValidator` 按 `stage1_schema`（设计 §B.7.1）校验，必填字段至少包含 `cycle_position`、`direction`、`diagnosis_confidence`、`market_phase`、`detected_patterns`、`key_signals`、`htf_context`、`entry_setup`、`strategy_files_needed`。
4. WHEN 阶段一 JSON 校验通过，THE System SHALL 调用 `StrategyRouter.route(stage1_json)` 得到策略文件列表，并执行阶段二。
5. THE 阶段二 system prompt SHALL 按以下顺序拼接：`提示词大纲_人设与思维方式.txt`、路由器返回的全部策略文件（保持顺序）、`文件17-止损和止盈与仓位管理.txt`、若有则追加最近 5 条经验库条目，再附上"决策输出格式（严格 JSON）"约束（设计 §B.3）。
6. THE 阶段二 user prompt SHALL 至少包含：阶段一诊断结果 JSON、与阶段一相同的 N 根 K 线表、不下单时三价段位必须为 null 的显式声明。
7. THE 阶段二 AI 响应 SHALL 通过 `JsonValidator` 按 `stage2_schema`（设计 §B.7.2）校验，必填字段至少包含 `decision.order_direction`、`decision.order_type`、`decision.entry_price`、`decision.take_profit_price`、`decision.stop_loss_price`、`decision.reasoning`、`decision.confidence`、`decision.key_factors`、`decision.watch_points`、`decision.risk_assessment`、`decision.invalidation_condition`、`diagnosis_summary.cycle_position`、`diagnosis_summary.direction`、`diagnosis_summary.key_signals`。
8. WHEN 调用 DeepSeek API，THE `DeepSeekClient` SHALL 始终带 `extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}, "reasoning_effort": <effort>}`，且 SHALL NOT 发送 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty` 任意一个（C2、设计 §B.2.3）。

---

### 需求 R6：高时间框架描述（HTF）由用户手动输入

**User Story:** 作为离散交易者，我想要在提交分析前手动输入更高时间框架的市场背景描述，以便 AI 在缺少 HTF 自动抓取的情况下仍能基于我的视角做诊断。

#### Acceptance Criteria

1. THE 主页 Tab1 SHALL 提供一个名为「HTF text」的多行文本输入框，且其内容随 `general.last_htf_text` 持久化（C4）。
2. WHEN 用户点击「提交分析」，THE System SHALL 把该输入框当前文本作为 `htf_text` 参数传给 `TwoStageOrchestrator.submit(...)`，并嵌入阶段一 user prompt 的「高时间框架背景」段落（C4、设计 §B.3）。
3. THE System SHALL NOT 自动从外部数据源抓取或推断 HTF 内容，且 `htf_text` 为空字符串时仍允许提交（仅在 user prompt 中保留空段落）。

---

### 需求 R7：提交分析时的 K 线快照策略

**User Story:** 作为离散交易者，我想要点击提交时的快照精确包含我看到的 N 根 bar（含当前未收盘那根作为 #1），以便 AI 看到的数据与我看到的图完全一致。

#### Acceptance Criteria

1. WHEN 用户点击「提交分析」，THE `KlineSnapshotter.take_snapshot(buffer, n)` SHALL 返回一个 `KlineFrame`，且 `len(frame.bars) == n`，其中 `n = general.default_bar_count`（默认 200，C8）。
2. THE 返回的 `frame.bars[0].seq` SHALL 等于 1，且 `frame.bars[0].closed` SHALL 等于 `False`（C6、C9）。
3. THE 序号集合 `{bar.seq | bar ∈ frame.bars}` SHALL 等于 `{1, 2, ..., n}`，即 1..n 的双射（设计 §B.5、性质 P1）。
4. FOR ALL 相邻索引 `i ∈ [0, n-1)`，THE 快照 SHALL 满足 `frame.bars[i].ts_open > frame.bars[i+1].ts_open`（时间严格倒序）。
5. THE 提交给 AI 的 K 线表 SHALL 与落盘到 `records/pending/...json` 的 `kline_data` 字段在字段集合、顺序与浮点位上完全相同（设计 §B.2.6、性质 P5）。
6. WHEN 快照已生成并冻结，THE 后续 1Hz 数据刷新 SHALL NOT 修改该 `KlineFrame`（不可变深拷贝，设计 §B.5）。

---

### 需求 R8：JSON 异常分类与跨提交的连续异常计数

**User Story:** 作为离散交易者，我想要任何 JSON 异常立刻终止流程并清晰报警，且连续异常会累计直到下次完整成功才清零，以便我可以及时判断是否要停用 AI 助手。

#### Acceptance Criteria

1. THE `JsonValidator` SHALL 按下列五类对失败分类：a 语法错误、b 字段缺失、c 值非法（含枚举/类型/不下单价非 null 等）、d 纯文本输出、e 连续异常（设计 §B.14、使用说明 §7）。
2. WHEN 阶段一或阶段二响应触发 a/b/c/d 任意一类，THE System SHALL 立即终止当前流水线，不再继续下一步，并通过 `PendingWriter.save_partial` 落盘已收集到的部分记录（设计 §B.7、§B.8）。
3. WHEN a/b/c/d 任意一类触发，THE `ExceptionCounter.consecutive_count` SHALL 自增 1，且 `last_error_category`、`last_error_at_ms` 同步更新；该状态 SHALL 持久化到 `D:\cl\PA_Agent\config\exception_state.json`（C10、设计 §B.8）。
4. WHEN 阶段一与阶段二在同一次提交中均通过校验，THE System SHALL 调用 `on_round_trip_success()` 把 `consecutive_count` 重置为 0；其它任何路径 SHALL NOT 重置该计数（C10、性质 P4）。
5. WHEN 程序重启，THE `ExceptionCounter` SHALL 从 `exception_state.json` 恢复 `consecutive_count`，使该计数对重启幂等（设计 §B.8）。
6. THE 报警载荷 `AlarmPayload` SHALL 至少包含字段：`category`（'a'..'e'）、`stage`（'阶段一-诊断' 或 '阶段二-决策'）、`timestamp_local_iso`、`raw_text`、`parse_position`（可空）、`missing_fields`、`invalid_fields`、`consecutive_count`、`history_excerpt`（最近 N 次）（设计 §B.8）。
7. WHILE `consecutive_count >= 2`，THE 主页「提交分析」按钮 SHALL 灰显，直到用户在 Tab3 点击「清除连续异常计数」并通过弹窗确认。
8. IF 触发原因是用户切换品种/周期或主动取消，THEN THE System SHALL NOT 自增 `consecutive_count`（C7、设计 §B.14）。
9. IF 触发原因是网络/HTTP 超时类错误，THEN THE System SHALL NOT 自增 `consecutive_count`，但 SHALL 在 Tab3 显示该次失败（设计 §B.14）。

---

### 需求 R9：「不下单」决策的规范形态

**User Story:** 作为离散交易者，当 AI 判断不宜入场时，我想要决策 JSON 与图表都准确表达「无入场」状态，以便我不会被遗留的入场/止损线误导。

#### Acceptance Criteria

1. WHEN `decision.order_type == "不下单"`，THE 阶段二 schema SHALL 强制要求 `decision.entry_price`、`decision.take_profit_price`、`decision.stop_loss_price`、`decision.order_direction` 全部等于 `null`（C11、设计 §B.7.2）。
2. WHEN `decision.order_type ∈ {"限价单", "突破单", "市价单"}`，THE 阶段二 schema SHALL 强制要求 `decision.entry_price`、`decision.take_profit_price`、`decision.stop_loss_price` 为有限实数，且 `decision.order_direction ∈ {"做多", "做空"}`（C11、设计 §B.7.2、性质 P3）。
3. IF `order_type == "不下单"` 且任一价格字段为 `0`、负数、字符串或非 null 的其它值，THEN THE `JsonValidator` SHALL 把该响应分类为 c（值非法）并终止流水线（C11、性质 P3）。
4. WHEN `order_type == "不下单"`，THE ChartWidget SHALL NOT 绘制 entry / take_profit / stop_loss 任何一条横线或标签（C11）。
5. WHEN `order_type == "不下单"`，THE 主页 `DecisionPanel` SHALL 仅显示文字结论与 `reasoning`，且不展示价格字段（C11、C13）。

---

### 需求 R10：三 Tab GUI 布局与每页职责

**User Story:** 作为离散交易者，我想要主页、对话页、调试页三个明确分工的 Tab，以便我可以分别快速查看决策、AI 完整思考、底层调试信息。

#### Acceptance Criteria

1. THE `MainWindow` SHALL 以 `QTabWidget` 形式至少提供三个 Tab：「主页」、「对话页」、「调试页」（C13）。
2. THE 主页 Tab1 SHALL 渲染：Symbol/Timeframe 下拉、BarCount 输入（默认 200）、HTF 文本输入、「提交分析」按钮、ChartWidget（含序号与 EMA20）、`DecisionPanel`、状态栏；当 `order_type ≠ "不下单"` 时 SHALL 在图表上叠加 entry/SL/TP 三条横线及标签（C13、设计 §B.11）。
3. THE 对话页 Tab2 SHALL 显示：阶段一与阶段二的完整 `reasoning_content` + `content`（含可折叠区块）、自由聊天消息流、文本输入框 + 发送按钮、token 进度条与累计费用文本（C13）。
4. THE 对话页 Tab2 的 token 指示器 SHALL 同时显示：`prompt_tokens + completion_tokens` 累计、占 `context_window`（默认 1_000_000）的百分比与进度条、按 `pricing.input_cache_hit / input_cache_miss / output` 三项分别核算的累计费用（设计 §B.9）。
5. WHEN 累计 `context_used / context_window * 100 >= cost_warning_threshold_pct`（默认 80%），THE 进度条 SHALL 切换为黄色；当 `>= 95%` SHALL 切换为红色并触发一次弹窗告警（设计 §B.9）。
6. THE 调试页 Tab3 SHALL 为本次会话每个轮次（Stage1 / Stage2 / Followup-N）至少展示四块内容：构造后的完整 system prompt、构造后的完整 user prompt、API 原始响应（含 HTTP 状态、headers、body、`reasoning_content`、`content`、`usage`、`request_id`）、本轮的校验/重试/异常分类（C13、设计 §B.11）。
7. THE Tab3 SHALL 提供「复制 system」「复制 user」「复制 response」「导出本轮 JSON」「清除连续异常计数」按钮，且导出文件落到 `records/pending/<basename>.debug-<turn>.json`（设计 §B.11）。

---

### 需求 R11：两阶段后的自由聊天会话

**User Story:** 作为离散交易者，我想要在两阶段分析完成后继续与模型对话，以便我可以追问、要求复盘或反向质询，且对话仍按 DeepSeek 的 reasoning 处理规则运行。

#### Acceptance Criteria

1. WHILE 当前提交未完整完成两阶段（任一阶段失败、被取消、或尚未点击提交），THE 对话页 Tab2 的输入框 SHALL 处于禁用状态。
2. WHEN 两阶段成功完成，THE `FreeChatSession` SHALL 被实例化并复用与阶段二完全相同的 system prompt（设计 §B.17）。
3. WHEN 用户在 Tab2 输入文本并点击发送，THE `FreeChatSession.send` SHALL 把消息追加到 `history_full`，并构造发往 API 的 `history_for_api`：`[system] + base_record.stage2_user_message + assistant(stage2_content) + 已有自由聊天轮次 + 新 user`（设计 §B.17）。
4. THE `FreeChatSession.send` SHALL 在当前作用域（非工具调用轮次）从重发历史中**丢弃** `reasoning_content`，但 SHALL 在 `history_full` 与持久化记录中保留全部 `reasoning_content`（C2、设计 §B.17）。
5. THE `FreeChatSession` SHALL 暴露开关 `keep_reasoning_in_resend`，使未来引入工具调用时只需翻转该开关即可在重发中保留 `reasoning_content`（C2、设计 §B.17、§B.20）。
6. WHEN 用户在请求进行中点击「停止」按钮，THE `FreeChatSession` SHALL 通过 `cancel_token.set()` 取消请求，并把当前轮次记为 `cancelled=True`，SHALL NOT 自增 `consecutive_count`（C7、C10、设计 §B.10）。
7. WHEN 一轮自由聊天成功返回，THE `SessionTokenLedger.add(usage)` SHALL 累加 `prompt_tokens`、`cached_prompt_tokens`、`completion_tokens` 与估算费用，且 Tab2 进度条与费用文本 SHALL 同步刷新（设计 §B.9）。

---

### 需求 R12：分析记录持久化

**User Story:** 作为离散交易者，我想要每次分析的完整上下文都自动写入磁盘，以便我事后可以复盘并手动归类。

#### Acceptance Criteria

1. WHEN 一次提交结束（成功或异常或取消），THE `PendingWriter` SHALL 把记录写入 `D:\cl\PA_Agent\records\pending\{YYYY-MM-DD_HH-mm-ss}_{symbol}_{timeframe}.json`，时间戳采用本机时区且取自用户点击「提交分析」的时刻（C14、设计 §7）。
2. THE `AnalysisRecord` 落盘字段 SHALL 至少包含：`meta.timestamp_local_iso`、`meta.timestamp_local_ms`、`meta.symbol`、`meta.timeframe`、`meta.bar_count`、`meta.ai_provider`（脱敏后的 provider 配置快照）、`kline_data`、`htf_text`、`stage1_messages`、`stage1_response`、`stage1_diagnosis`、`stage2_messages`、`stage2_response`、`stage2_decision`、`strategy_files_used`、`experience_loaded`、`exception`（可空）、`usage_total`（C14、设计 §B.2.6）。
3. THE `meta.ai_provider` SHALL NOT 包含明文 API key；该字段中任意 API key 形态的子串 SHALL 被替换为 `mask_secret(key)` 形式（C3、C14、性质 P6）。
4. WHEN 自由聊天产生新一轮，THE `PendingWriter.append_followup(record_id, turn, user_text, reply)` SHALL 把该轮以单行 JSON 追加到 `<basename>.followups.jsonl`，每行字段至少包含 `turn`、`ts_ms`、`user`、`ai_content`、`ai_reasoning`、`usage`、`cancelled`（C14、设计 §B.17）。
5. FOR ALL 合法 `AnalysisRecord` 实例 r，THE 序列化-反序列化 SHALL 满足 `AnalysisRecord.parse_obj(json.loads(json.dumps(r.dict()))) == r`（深度相等，含 `kline_data` 顺序与浮点位）（性质 P5）。
6. IF 写入磁盘失败（权限、磁盘满等），THEN THE System SHALL 在 Tab3 与日志中记录失败原因，但 SHALL NOT 让异常冒泡到 UI 主线程导致崩溃。

---

### 需求 R13：经验库读取（程序只读，用户手动维护）

**User Story:** 作为离散交易者，我想要程序在阶段二自动加载我手动整理过的最近成功/失败案例，以便 AI 能从我过去的判断中获益。

#### Acceptance Criteria

1. THE `ExperienceReader.read_top5(cycle_position)` SHALL 仅读取 `D:\cl\PA_Agent\experience\{cycle_position}\success_cases\` 与 `D:\cl\PA_Agent\experience\{cycle_position}\failure_cases\` 两个目录，且 SHALL NOT 写入或删除其中任何文件（C15、设计 §B.16）。
2. THE 排序键 SHALL 是文件名中嵌入的时间戳 `YYYY-MM-DD_HH-mm-ss`（解析为毫秒），SHALL 按降序排列，并取前 5 条（C12、性质 P1 不直接相关）。
3. WHEN 经验库目录不存在或为空，THE `ExperienceReader.read_top5` SHALL 返回空列表，且阶段二 SHALL 仍能正常执行，仅在 system prompt 中省略经验库段落（设计 §B.3）。
4. WHEN 任一文件名无法被解析为合法时间戳，THE System SHALL 在日志中记录警告并跳过该文件，但 SHALL NOT 抛出未捕获异常。
5. THE 加载到阶段二的所有条目 SHALL 通过 `experience_loaded` 字段写入 `AnalysisRecord`，便于事后复盘（C14、设计 §B.2.6）。

---

### 需求 R14：诊断 → 策略文件路由规则

**User Story:** 作为离散交易者，我想要程序按使用说明 §11 的路由表确定性地决定阶段二加载哪些策略文件，以便相同的诊断结果总是触发相同的策略组合。

#### Acceptance Criteria

1. THE `StrategyRouter.route(stage1_json)` SHALL 是确定性纯函数：对相同输入 SHALL 返回完全相同的列表（值与顺序均一致）（设计 §B.4、性质 P2）。
2. WHEN `cycle_position ∈ {micro_channel, tight_channel, normal_channel, broad_channel}` 且 `direction == "bullish"`，THE Router SHALL 返回（按顺序）`["上涨通道分析识别.txt", "上涨通道交易策略.txt", "文件13-窄通道与宽通道策略.txt"]`，再按形态追加。
3. WHEN `cycle_position ∈ {micro_channel, tight_channel, normal_channel, broad_channel}` 且 `direction == "bearish"`，THE Router SHALL 返回（按顺序）`["下跌通道分析识别.txt", "下跌通道交易策略.txt", "文件13-窄通道与宽通道策略.txt"]`，再按形态追加。
4. WHEN `cycle_position ∈ 通道集合` 且 `direction == "neutral"`，THE Router SHALL 跳过通道分析与交易策略文件，但 SHALL 仍追加 `文件13-窄通道与宽通道策略.txt`，并 SHALL 写入 `log_warning("Channel state with neutral direction")`（设计 §B.4）。
5. WHEN `cycle_position == "spike"` 且 `direction == "bullish"`，THE Router SHALL 返回（按顺序）`["极速上涨分析识别.txt", "极速上涨交易策略.txt"]`，再按形态追加。
6. WHEN `cycle_position == "spike"` 且 `direction == "bearish"`，THE Router SHALL 返回（按顺序）`["极速下跌分析识别.txt", "极速下跌交易策略.txt"]`，再按形态追加。
7. WHEN `cycle_position == "spike"` 且 `direction == "neutral"`，THE Router SHALL 不追加任何尖峰文件，并 SHALL 写入 `log_warning("Spike with neutral direction")`。
8. WHEN `cycle_position ∈ {trading_range, trending_tr}`，THE Router SHALL 返回（按顺序）`["震荡区间分析识别.txt", "震荡区间交易策略.txt"]`，再按形态追加。
9. WHEN `cycle_position ∈ {extreme_tr, unknown}`，THE Router SHALL 返回不含任何策略文件的列表（仅可能因形态追加），并代表「不交易」语义。
10. IF `"wedge" ∈ detected_patterns`，THEN THE Router SHALL 把 `文件14-楔形形态分析交易.txt` 追加到列表末尾。
11. IF `"reversal_attempt" ∈ detected_patterns`，THEN THE Router SHALL 把 `文件15-二次入场机会.txt` 追加到列表末尾。
12. THE Router SHALL 对最终列表执行稳定去重（保留首次出现位置），且 SHALL NOT 引入使用说明清单外的任何文件名（性质 P2）。

---

### 需求 R15：Token 预算与 1M 上下文窗监控

**User Story:** 作为离散交易者，我想要 GUI 实时反映本会话 token 用量与花费，以便我可以在接近上下文窗上限或预算阈值前停手。

#### Acceptance Criteria

1. THE `SessionTokenLedger` SHALL 跟踪四个累计量：`total_input`、`total_cached_input`、`total_output`、`total_cny`；且 `context_used = total_input + total_output`（设计 §B.9）。
2. THE `CostEstimator.estimate_cost(usage, pricing)` SHALL 按公式 `(cached_hit * input_cache_hit + (prompt - cached_hit) * input_cache_miss + completion * output) / 1_000_000` 计算单次费用，单位为人民币（设计 §B.9）。
3. WHEN 任意一次 API 调用返回 `usage`，THE Ledger SHALL 调用 `add(usage)` 更新累计值，且对话页 Tab2 SHALL 在 200 ms 内刷新进度条与费用文本。
4. WHEN `context_used / context_window * 100 >= cost_warning_threshold_pct`（默认 80），THE Ledger SHALL 触发一次黄色告警；当 `>= 95` SHALL 触发一次红色告警 + 弹窗（设计 §B.9）。
5. THE `DeepSeekClient.chat` SHALL NEVER 发送 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty` 任意一个，无论用户配置如何（C2、设计 §B.2.3）。
6. THE 调试页 Tab3 SHALL 为每一轮显示「`tiktoken` 预估 token 数」与「服务端 `usage` 实际 token 数」并排比较（设计 §B.9）。

---

### 需求 R16：线程模型与响应性

**User Story:** 作为离散交易者，我想要 UI 在 1Hz 数据刷新与长时间 AI 调用期间始终保持响应，以便我可以随时切换品种、查看图表或取消请求。

#### Acceptance Criteria

1. THE 1Hz `RefreshLoop` SHALL 运行在专用 `QThread` 中，且 SHALL 通过 `pyqtSignal` 把帧推送给 UI 线程（设计 §6）。
2. THE AI worker SHALL 运行在专用 `QThread` 中，且每个时刻 SHALL 至多存在一个活跃的 worker；新提交 SHALL 先取消旧 worker 再启动（设计 §6、§B.10）。
3. THE UI 主线程 SHALL NOT 直接调用 `DeepSeekClient.chat`、`DataSource.fetch_recent` 或 `json.loads(big)`（设计 §B.19 不变量 8）。
4. THE ChartWidget SHALL 通过一个 30 Hz 的 `QTimer` 节流重绘，避免 1Hz 数据线程把绘制压力压回 UI 主线程（设计 §6）。
5. WHEN 用户点击 Tab2 的「停止」、Tab1 的「切换品种/周期」或关闭主窗口，THE 当前 AI worker 的 `cancel_token.is_set()` SHALL 在 100 ms 内变为 True，且 worker 的 HTTP 客户端 SHALL 尝试关闭流（设计 §B.10）。
6. WHILE 数据源连续异常或网络抖动，THE `RefreshLoop` SHALL 仅在状态栏显示「数据延迟」，且 SHALL NOT 让异常冒泡到 UI 主线程（设计 §6）。

---

### 需求 R17：本地文件安全

**User Story:** 作为离散交易者，我想要 API key 永远不会以明文形式落盘或出现在调试视图，以便我的账户安全在程序层面被强制保障。

#### Acceptance Criteria

1. THE `SecretStore` SHALL 在 Windows 上使用 DPAPI、在其它平台使用 `cryptography.fernet` + 用户目录密钥盐对 API key 加密；密文以 base64 字符串存入 `settings.json` 的 `api_key_encrypted`（设计 §B.12）。
2. THE 日志文件 `D:\cl\PA_Agent\logs\pa_agent.log` SHALL 经过 `RotatingFileHandler` 轮转，且 SHALL NEVER 以明文写入 API key（设计 §B.12）。
3. FOR ALL 写入日志、记录、Tab3 调试视图的字符串 s，THE System SHALL 保证 `provider.api_key` 的明文 SHALL NOT 作为子串出现在 s 中（性质 P6、设计 §B.19 不变量 6）。
4. THE `SettingsDialog` SHALL 默认以密码模式渲染 API key 输入框，且任何「显示」切换 SHALL NOT 触发持久化（设计 §B.12）。
5. WHEN `settings.json` 写盘，THE System SHOULD 在支持的平台上把文件权限设为仅当前用户可读写（受 OS 限制时记录警告但不视为致命错误）。
6. THE `mask_secret` 函数 SHALL 对长度大于等于 4 的密钥返回 `"*" * (len(s) - 4) + s[-4:]`，对长度小于 4 的密钥（含空串）原样返回（设计 §B.12）。

---

### 需求 R18：错误报告 UX 与无静默重试

**User Story:** 作为离散交易者，我想要每次异常都立即展示在 UI 上并带完整调试信息，且程序不会偷偷重试改输出，以便我能信任屏幕上看到的每一条 AI 决策。

#### Acceptance Criteria

1. WHEN `JsonValidator` 返回任意 a/b/c/d 类异常，THE System SHALL 在 100 ms 内同时在状态栏（简短文字）、Tab3（完整 `AlarmPayload`）、模态弹窗（最关键字段摘要）三处呈现报警（设计 §B.8、§B.14）。
2. THE 弹窗最后一行 SHALL 显示「流程已终止，请检查后重试」原文（使用说明 §7、设计 §B.8）。
3. WHILE `consecutive_count >= 2`，THE 状态栏顶部 SHALL 显示置顶横幅，列出最近 N 次异常摘要（设计 §B.14）。
4. THE System SHALL NEVER 在校验失败后自动用同一 prompt 重试并替换原始响应；任何重试 SHALL 由用户显式触发（再次点击「提交分析」或在 Tab3 触发导出后人工排查）。
5. THE Tab3 SHALL 为每个轮次保留：原始响应文本（含 markdown fence）、解析位置（行:列）、缺失字段列表、非法字段列表与允许集合（设计 §B.7、§B.8）。
6. WHEN 异常归类为取消或网络/超时类，THE System SHALL 在 Tab3 单独标注，且 SHALL NOT 把它显示为「连续异常」相关（设计 §B.14）。

---

## 4. 范围之外（Out of Scope）

下列能力**不**属于本特性的目标，未来若需要将开新的 spec：

- 自动下单、撤单、改仓、持仓管理或与任何券商/经纪商接口的连接；
- 自动把 `records/pending/` 中的记录归类为成功或失败案例（必须用户手动移动到 `experience/...` 子目录）；
- 自动从 TradingView 或其它源抓取更高时间框架背景（HTF 必须由用户手动输入，C4）；
- 除 JSON Schema 外的硬编码风控（不做「价格合理性」「最小止损」等业务校验，使用说明 §13）；
- 多用户/多账户共享配置或云同步；
- AI 模型微调、本地部署或 RAG 向量检索；
- 经验库自动归类建议或自动盈亏统计（属于另一个独立 spec，设计 §B.20）；
- 在 Linux 或 macOS 上对 TradingView 数据源做生产级支持（当前仅 Windows 桌面，C1 + 设计 §B.12）；
- MT5 数据源的实际生产可用实现（仅保留接口 stub，C1）。

---

## 5. 性质化正确性需求（Property-Based Correctness Requirements）

下列需求与设计文档 §B.13 的 P1–P8 一一对应，每条以单个可测的 EARS 验收准则呈现，便于 `hypothesis` 性质测试直接消费。

### PR1：快照序号双射

**User Story:** 作为开发者，我想要 `take_snapshot` 在所有合法输入上保持序号语义，以便 AI 引用序号 N 时永远指向同一根 bar。

#### Acceptance Criteria

1. FOR ALL `n >= 2` 与所有缓冲容量 `c >= n` 的有效 `KlineBuffer`，THE `take_snapshot(buffer, n)` SHALL 返回的 `KlineFrame` 满足：(i) `len(bars) == n`；(ii) `{bar.seq | bar ∈ bars} == {1, ..., n}`；(iii) `bars[0].seq == 1` 且 `bars[0].closed == False`；(iv) `bars[i].ts_open > bars[i+1].ts_open` 对所有 `i ∈ [0, n-1)` 成立（对应设计性质 P1）。

### PR2：路由器确定性与幂等

**User Story:** 作为开发者，我想要路由器对相同诊断永远给出相同策略文件列表，以便阶段二 system prompt 在重复输入下完全一致。

#### Acceptance Criteria

1. FOR ALL 通过阶段一 schema 校验的 `stage1_json`，THE `route_strategy_files(stage1_json)` SHALL 满足：(i) `route(s) == route(s)`（确定性）；(ii) `route(s)` 的元素全部位于使用说明 §3+§4 给出的 17 文件清单内；(iii) 元素唯一（稳定去重）；(iv) `route(route_subset(s))` 不会引入新的文件（对应设计性质 P2）。

### PR3：阶段二「不下单」铁律

**User Story:** 作为开发者，我想要阶段二校验器在「不下单/有下单」两侧都强制约束，以便 GUI 不会画出错误的入场线。

#### Acceptance Criteria

1. FOR ALL 阶段二决策对象 d，THE `JsonValidator.validate_stage2(d)` SHALL 满足：当 `d.decision.order_type == "不下单"` 时，仅当 `entry_price`、`take_profit_price`、`stop_loss_price`、`order_direction` 全部为 `null` 才接受；当 `d.decision.order_type ∈ {"限价单","突破单","市价单"}` 时，仅当上述四字段全部非 null 且 `order_direction ∈ {"做多","做空"}` 才接受；其它任意组合一律拒绝并归类为 c（对应设计性质 P3）。

### PR4：连续异常计数器单调性

**User Story:** 作为开发者，我想要异常计数器在任意失败序列上单调非减，且仅由完整成功重置，以便熔断机制可信。

#### Acceptance Criteria

1. FOR ALL 由 `Validation_Error` 与 `Round_Trip_Success` 组成的事件序列 E，THE `ExceptionCounter` SHALL 满足：(i) 每个 `Validation_Error` 后 `consecutive_count` 单调非减；(ii) 每个 `Round_Trip_Success` 立刻把 `consecutive_count` 重置为 0；(iii) 进程重启后从 `exception_state.json` 恢复的计数等于重启前的值（对应设计性质 P4）。

### PR5：分析记录序列化往返

**User Story:** 作为开发者，我想要分析记录在 JSON 序列化-反序列化下保持深度相等，以便归类到经验库的记录与原始记录字字相同。

#### Acceptance Criteria

1. FOR ALL 合法 `AnalysisRecord` 实例 r，THE 系统 SHALL 满足 `AnalysisRecord.parse_obj(json.loads(json.dumps(r.dict()))) == r`，含 `kline_data` 顺序、浮点位、`reasoning_content` 与所有可选字段（对应设计性质 P5）。

### PR6：API key 脱敏不变量

**User Story:** 作为开发者，我想要任何写入日志或调试视图的字符串都不含 API key 明文，以便密钥泄漏在程序层面被强制阻断。

#### Acceptance Criteria

1. FOR ALL 在 `D:\cl\PA_Agent\logs\`、Tab3 调试视图、`records\pending\` 目录中产生的字符串 s，THE 系统 SHALL 保证 `provider.api_key` 的明文 NOT IN s（即明文不作为子串出现），且任何形如 `sk-[A-Za-z0-9]{12,}` 的串若与当前明文一致 SHALL 被替换为 `mask_secret` 形式（对应设计性质 P6）。

### PR7：JSON 校验类别正确性

**User Story:** 作为开发者，我想要校验器对每一类失败给出正确的分类标签，以便用户在报警里看到准确的错误归因。

#### Acceptance Criteria

1. FOR ALL 文本 t 与阶段 stage，THE `JsonValidator.validate(stage, t)` SHALL 满足：(i) 通过 schema 的 JSON 必接受；(ii) 仅有语法错误的输入归类为 a；(iii) 仅缺必填字段的输入归类为 b；(iv) 字段存在但值非法（枚举/类型/不下单价非 null）的输入归类为 c；(v) 完全不含 JSON 结构的纯文本归类为 d（对应设计性质 P7）。

### PR8：指标增量与全量等价

**User Story:** 作为开发者，我想要 EMA20 与 ATR14 在「全量重算」与「追加 1 根的增量更新」下产生一致结果，以便 AI 看到的指标与 UI 显示的指标完全一致。

#### Acceptance Criteria

1. FOR ALL 浮点序列 `values` 与窗口 `period`，THE `ema(values, period)` 与 `atr(highs, lows, closes, period)` SHALL 满足：(i) 相同输入产出相同输出；(ii) 对长度 ≥ period 的输入 v 与单点 x，`ema(v + [x])[-1] == ema_incremental(state, x).last` 与 `atr(...)` 同理（增量末项等于全量末项）；(iii) NaN 出现位置稳定（前 period-1 项为 NaN，后续无 NaN）（对应设计性质 P8）。
