# 参与贡献

感谢你对 IQ 的关注。本项目欢迎 Issue 与 Pull Request。

## 开发环境

1. Windows 10/11，Python 3.11+。桌面端和 MT5 联调主要面向 Windows。
2. Node.js 18+。仅开发 `apps/web` 的 Next.js 前端时需要。
3. 克隆仓库后初始化 Python 环境：

   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e ".[dev]"
   copy config\settings.example.json config\settings.json
   ```

4. 如需运行 Web 前端：

   ```cmd
   cd apps\web
   pnpm install
   pnpm dev
   ```

5. 在 GUI **设置** 中配置 API Key，或仅跑不依赖网络的测试。

## 常用检查

Python：

```cmd
python -m pytest -m "not e2e"
ruff check candle_cast tests
```

Web：

```cmd
cd apps\web
pnpm test
pnpm typecheck
pnpm build
```

（若已安装 `black`，可按团队习惯格式化。）

## 请勿提交

- `config/settings.json`、`config/exception_state.json`
- `logs/`、`records/pending/`、`experience/` 下的运行数据
- 任何 API Key、`.env`、私钥文件

启用本地 pre-commit 钩子：

```powershell
powershell -ExecutionPolicy Bypass -File tools\setup_git_secrets.ps1
```

## Pull Request 建议

- 一个 PR 聚焦一类改动（功能 / 修复 / 文档）
- 说明动机与测试方式
- 若改 JSON schema、提示词、FastAPI 路由或 Web API 类型，请补充或更新相关 Python/Vitest 用例

## 问题反馈

- Bug：附上日志片段（`logs/candle_cast.log`）、复现步骤、品种/周期、使用的是桌面端还是 Web 端
- 功能建议：说明使用场景与期望行为

讨论与交流也可加入 README 中的 QQ 群。
