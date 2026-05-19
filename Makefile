.PHONY: run test lint

# 启动 GUI
run:
	python -m pa_agent.main

# 运行测试
test:
	pytest -q

# 代码检查
lint:
	ruff check . && black --check .
