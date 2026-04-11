# Contributing to Marmot

Thank you for your interest in contributing to Marmot! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)

## Code of Conduct

Be respectful and constructive. We welcome contributions from everyone.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yxkaze/marmot.git`
3. Create a branch: `git checkout -b feature/your-feature-name`

## Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Install development dependencies
pip install -e ".[dev]"

# Install additional tools
pip install black isort mypy

# Run tests to verify setup
pytest -v
```

## Making Changes

### Project Structure

```
marmot/
├── src/marmot/          # Core source code
│   ├── __init__.py      # Public API exports
│   ├── models.py        # Domain models
│   ├── app.py           # Core engine + state machine
│   ├── storage.py       # SQLite persistence
│   ├── notifiers.py     # Notification channels
│   ├── web.py           # Web console
│   └── bucket.py        # Metric aggregation
├── tests/               # Test suite
├── examples/            # Usage examples
├── docs/                # Documentation
└── skills/marmot/       # AI skill knowledge base
```

### Key Principles

1. **Zero Dependencies**: Keep runtime dependencies minimal (stdlib + SQLite only)
2. **Type Annotations**: All public APIs must have type hints
3. **Docstrings**: All public functions/classes need docstrings
4. **Backward Compatibility**: Don't break existing APIs without major version bump

## Testing

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_app.py -v

# Run with coverage
pytest --cov=src/marmot --cov-report=html

# Run specific test
pytest tests/test_app.py::test_report_threshold -v
```

### Writing Tests

- Use `FakeNotifier` from `tests/test_app.py` for capturing notifications
- Use `:memory:` SQLite for test isolation
- Test edge cases: threshold boundaries, state transitions, error handling

## Code Style

We use the following tools:

```bash
# Format code
black src/ tests/
isort src/ tests/

# Check formatting
black --check src/ tests/
isort --check-only src/ tests/

# Type check
mypy src/marmot
```

### Style Guidelines

- Line length: 100 characters
- Use dataclasses with `slots=True` for data structures
- Prefer composition over inheritance
- Use `typing` module for type hints

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add support for Slack notifications
fix: resolve duplicate alert issue in silence window
docs: update API reference for ThresholdRule
test: add tests for metric aggregation
refactor: simplify state machine transitions
chore: update CI workflow
```

## Pull Requests

### Before Submitting

- [ ] Tests pass: `pytest -v`
- [ ] Code is formatted: `black --check src/ tests/`
- [ ] Imports are sorted: `isort --check-only src/ tests/`
- [ ] Type checks pass: `mypy src/marmot`
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated (if applicable)

### PR Process

1. Create a descriptive PR title
2. Link related issues
3. Describe your changes
4. Wait for CI to pass
5. Address review feedback

### PR Title Format

```
feat: short description
fix: short description
docs: short description
test: short description
refactor: short description
```

## Questions?

Open an issue for bugs, feature requests, or questions.

Thank you for contributing!
