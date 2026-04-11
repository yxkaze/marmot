# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CI/CD with GitHub Actions
- Code quality tools (black, isort, mypy)
- Test coverage reporting with pytest-cov
- Makefile for common development tasks
- GPL v3 license
- Contributing guidelines

## [0.1.0] - 2024-04-11

### Added

- **Core Alert Engine**
  - Threshold-based alerting with multi-level thresholds
  - Alert state machine: PENDING → FIRING → RESOLVED
  - SILENCED and ESCALATED state branches
  - Automatic deduplication by rule_name + labels
  - Configurable silence windows
  - Escalation with configurable steps

- **Monitoring Features**
  - Job monitoring with `@marmot.job()` decorator
  - Heartbeat monitoring with `ping()` API
  - Metric aggregation with sliding window (avg/max/min/sum/count)
  - Manual alert fire and resolve

- **Notification Channels**
  - ConsoleNotifier for development
  - WebhookNotifier for generic webhooks
  - MarkdownWebhookNotifier for Slack/Discord
  - DingTalkNotifier with HMAC signing
  - WeComNotifier for Enterprise WeChat
  - FeishuNotifier with card messages
  - EmailNotifier (callback mode, zero dependencies)
  - PhoneNotifier for critical alerts

- **Web Interface**
  - Built-in HTTP server (zero dependencies)
  - Real-time dashboard with auto-refresh
  - REST API endpoints for alerts, history, runs, notifications, rules

- **Persistence**
  - SQLite storage for alert history
  - Run records for jobs and heartbeats

- **Developer Experience**
  - Module-level API for simple use cases
  - MarmotApp class for advanced scenarios
  - Full type annotations
  - Comprehensive docstrings

[unreleased]: https://github.com/yxkaze/marmot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yxkaze/marmot/releases/tag/v0.1.0
