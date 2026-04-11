# =============================================================================
# Marmot 开发命令
# =============================================================================
# 使用方法：
#   make test        # 运行测试
#   make lint        # 代码检查
#   make format      # 格式化代码
#   make coverage    # 测试覆盖率报告
#   make build       # 构建包
#   make clean       # 清理构建产物
# =============================================================================

.PHONY: test lint format coverage build clean help

# 默认目标
help:
	@echo "Marmot 开发命令："
	@echo "  make test        运行测试"
	@echo "  make lint        代码检查 (black, isort, mypy)"
	@echo "  make format      格式化代码"
	@echo "  make coverage    测试覆盖率报告 (HTML)"
	@echo "  make build       构建包"
	@echo "  make clean       清理构建产物"
	@echo "  make install     安装开发依赖"
	@echo "  make all         运行所有检查"

# 安装开发依赖
install:
	pip install -e ".[dev]"

# 运行测试
test:
	pytest -v

# 测试覆盖率报告
coverage:
	pytest --cov=src/marmot --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "覆盖率报告已生成: htmlcov/index.html"

# 代码检查
lint:
	@echo "=== Black 检查 ==="
	black --check --diff src/ tests/
	@echo ""
	@echo "=== isort 检查 ==="
	isort --check-only --diff src/ tests/
	@echo ""
	@echo "=== Mypy 类型检查 ==="
	mypy src/marmot --ignore-missing-imports

# 格式化代码
format:
	black src/ tests/
	isort src/ tests/
	@echo "代码格式化完成"

# 构建包
build:
	python -m build
	@echo ""
	@echo "构建产物在 dist/ 目录"

# 检查包
check-build:
	twine check dist/*

# 清理构建产物
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "清理完成"

# 运行所有检查
all: lint test
	@echo ""
	@echo "所有检查通过！"
