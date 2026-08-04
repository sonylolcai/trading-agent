# 全流程量能 A/B 回测

`pa_agent.backtest.full_flow` 不使用滚动回测中的代理入场逻辑，而是以每个历史时点的 K 线快照重放完整流程：

```text
共同的纯价格预筛选
  → 各组简化 LLM 筛选
  → Stage 1
  → 策略路由 / Stage 2
  → 原有 JSON 校验与订单修正
  → 保守交易模拟
```

`price_only` 不接收量能上下文。`volume_assisted` 在简化筛选、Stage 1、Stage 2 都额外接收同一份只读量能上下文：K1 成交量、K2-K21 均量、相对量能和 K1 收盘位置。价格行为依然是主导条件；量能不能单独生成入场或推翻风控。

## 防偏差约束

- 每个快照只使用该历史时点及更早的 K 线；量能均线使用 K2-K21，不读取未来数据。
- 两组共用纯价格预筛选的候选时间戳和候选上限；之后简化 LLM 的筛选结果允许不同，这是被比较的策略差异。
- 单标的单活动仓位、同 K 线同时触及止损和止盈时按止损处理，并可指定最大持有期。
- 历史 setup 统计和经验库在此运行中禁用，避免将后续样本反馈给较早时点。
- LLM 缓存键包含完整快照、实验组、模型版本和提示词版本；更换任一项会重新调用模型。

## 运行

数据必须已经存在于项目 K 线缓存。下列命令会调用配置中的模型，消耗 Token；第一次运行建议只保留 20 个共同候选。

```powershell
python tools/run_full_flow_volume_ab_backtest.py `
  --source yfinance --symbol 600519.SS --timeframe 1d `
  --window 100 --max-candidates 20 --max-holding-bars 30
```

结果写入 `reports/full_flow_volume_ab.json`，包含每组的候选数、简化筛选淘汰数、完整流程调用数、失败数、完成交易、胜率、期望 R、总 R、最大回撤、Token 和延迟。研究记录与生产 pending records 分开保存。

这个工具用于验证量能辅助是否在完整 PA 流程中带来稳健增益；单次样本中表现较好不构成生产接入依据。
