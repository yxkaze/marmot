# Marmot — Agent Guidance

## Commands

- **Install**: `pip install -e .`
- **Dev install**: `pip install -e ".[dev]"`
- **Test**: `pytest -v`
- **Run example**: `python examples/quickstart.py`

## Architecture

- **Entry point**: `src/marmot/__init__.py` exports module-level API
- **Core**: `app.py` — state machine + main engine; `models.py` — domain types
- **Package**: Single `marmot` package, no monorepo
- **Storage**: SQLite (created on first `configure()` call)

## Key Facts

- **Init required**: Must call `marmot.configure("alerts.db")` before using any API
- **State machine**: `PENDING → FIRING → RESOLVING → RESOLVED`, with `SILENCED`/`ESCALATED` branches
- **No runtime deps**: Pure Python stdlib + SQLite
- **Python**: 3.10+

## Reference

- Domain knowledge: see `skills/marmot/SKILL.md`
- API details: see `skills/marmot/references/api-reference.md`
- Examples: see `skills/marmot/references/examples.md`