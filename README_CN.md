# Marmot (土拨鼠) — Python 轻量级告警框架

[![PyPI version](https://img.shields.io/pypi/v/marmot-alert.svg)](https://pypi.org/project/marmot-alert/)
[![Python versions](https://img.shields.io/pypi/pyversions/marmot-alert.svg)](https://pypi.org/project/marmot-alert/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/yxkaze/marmot/actions/workflows/ci.yml/badge.svg)](https://github.com/yxkaze/marmot/actions/workflows/ci.yml)

一个面向开发者的、零依赖的轻量级告警框架，专注于**简洁**与**实用**。注册规则、上报指标，剩下的交给 Marmot：状态机、去重、静默窗口、升级机制、多渠道通知。

**[English](README.md)** | 简体中文

## 为什么选择 Marmot？

| 特性 | 说明 |
|------|------|
| **零依赖** | 纯 Python 标准库 + SQLite，无外部依赖 |
| **状态机** | 完整的告警生命周期：PENDING → FIRING → RESOLVED |
| **多渠道通知** | 钉钉、飞书、企微、邮件、Webhook、电话 |
| **自动去重** | 基于 rule_name + labels 自动去重 |
| **静默窗口** | 抑制重复告警，避免告警风暴 |
| **升级机制** | 超时后自动升级到更高级别通知 |
| **Job 监控** | 装饰器模式，零侵入监控定时任务 |
| **心跳检测** | 存活监控，自动恢复 |
| **内置 Web 面板** | 实时仪表盘，访问 localhost:8765 |

## 安装

```bash
pip install marmot-alert
```

## 快速开始

### 1. 初始化

```python
import marmot

# 初始化，使用 SQLite 持久化
marmot.configure("alerts.db")
```

### 2. 注册通知渠道

```python
# 控制台（开发调试用）
marmot.register_notifier("console", marmot.ConsoleNotifier())

# 钉钉
marmot.register_notifier("ding", marmot.DingTalkNotifier(
    webhook_url="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
    secret="YOUR_SECRET",  # 可选，HMAC 签名
))

# 飞书
marmot.register_notifier("feishu", marmot.FeishuNotifier(
    webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN",
    secret="YOUR_SECRET",
))

# 企业微信
marmot.register_notifier("wecom", marmot.WeComNotifier(
    webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY",
))

# 邮件（零依赖，回调模式）
marmot.register_notifier("email", marmot.EmailNotifier(
    send_fn=你的发送邮件函数,
    to=["oncall@example.com"],
))
```

### 3. 阈值告警

```python
# 注册阈值规则
marmot.register_threshold_rule(marmot.ThresholdRule(
    name="cpu_usage",
    thresholds=[
        marmot.ThresholdLevel(value=80, severity="warning"),
        marmot.ThresholdLevel(value=95, severity="critical"),
    ],
    consecutive_count=3,      # 连续 3 次超阈值才触发
    silence_seconds=300,      # 触发后静默 5 分钟
    notify_targets=["ding"],
))

# 上报指标（代码里只需要这一行）
marmot.report("cpu_usage", 92.5, labels={"host": "prod-1"})
```

### 4. Job 监控

```python
@marmot.job("data_pipeline", expected_interval="5m", timeout="10m", notify="ding")
def run_pipeline():
    process_data()
    # 失败自动告警，成功自动恢复
```

### 5. 心跳监控

```python
# 注册心跳规则
marmot.register_rule(marmot.Rule.from_inputs(
    name="worker_heartbeat",
    expected_interval="30s",
    timeout="2m",
    notify="ding",
))

# 在 worker 中定期调用
marmot.ping("worker_heartbeat", labels={"worker_id": "w-01"})
```

### 6. 手动告警

```python
# 直接触发告警
marmot.fire(
    "payment_failure",
    "支付网关超时 — 连续 5 次失败",
    severity="critical",
    labels={"service": "payments"},
    notify_targets=["ding", "email"],
)

# 手动恢复
marmot.resolve("payment_failure", message="网关已恢复")
```

## 告警状态机

```
 report()         report()        静默窗口到期        升级计时器
首次触发 ──► PENDING ──► FIRING ──────────────► FIRING ──────────────► ESCALATED
            (计数中)        │
                           │ report(正常) 连续N次
                           ▼
                        RESOLVING ──► RESOLVED
                         (确认中)       (已恢复)
```

## 指标聚合

监控多个实例的聚合指标：

```python
marmot.register_threshold_rule(marmot.ThresholdRule(
    name="es_disk",
    thresholds=[marmot.ThresholdLevel(value=85, severity="warning")],
    aggregate=marmot.AggregateConfig(fn="avg", window=300),  # 5分钟窗口平均值
    notify_targets=["ding"],
))

# 各实例独立上报，框架自动聚合
for cluster in clusters:
    marmot.report("es_disk", disk_usage, labels={"cluster": cluster.name})
```

支持的聚合函数：`avg`、`max`、`min`、`sum`、`count`。

## Web 仪表盘

```python
# 启动内置 Web 服务器
ui = marmot.start_ui_server(host="0.0.0.0", port=8765)
# 访问 http://localhost:8765

# 关闭
ui.stop()
```

API 端点：`/api/alerts`、`/api/history`、`/api/runs`、`/api/notifications`、`/api/rules`。

## 文档

- [API 参考](skills/marmot/references/api-reference.md)
- [使用示例](skills/marmot/references/examples.md)


## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest -v

# 测试覆盖率
pytest --cov=src/marmot --cov-report=html

# 代码格式化
black src/ tests/
isort src/ tests/

# 类型检查
mypy src/marmot
```

## 其他语言版本

- **Python** — 当前版本
- **Go** — 计划中

## 许可证

Apache License 2.0。详见 [LICENSE](LICENSE)。

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。
