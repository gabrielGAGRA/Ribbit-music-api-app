# Backend (`app/`)

Python 3.15 + FastAPI + SQLite + GCS/Parquet backend organized with Hexagonal Architecture (Ports & Adapters) and DDD.

## Layout & Boundaries

- `app/domain/`: pure entities, value objects, domain services, and `CustomError` hierarchy (`exceptions.py`). No transport/HTTP or infrastructure imports.
- `app/application/`: use cases (`use_cases/`), DTOs (`dtos/`), and repository/service interfaces (`ports/`).
- `app/infrastructure/`: SQLite repositories (`repositories/`), external adapters (`adapters/`: Spotify, iTunes, Google OAuth, GCS/Parquet), security, telemetry.
- `app/presentation/`: FastAPI routers (`routers/`), Pydantic schemas (`schemas/`), dependencies, middleware, exception-to-HTTP mapping.
- `app/composition/`: dependency wiring (`container.py`, `app_factory.py`) and `app/config.py`.

## Quality Gate & Tests

Run via `.venv` (or active Python 3.15 environment) after edits in `app/`:

```bash
ruff format app tests
ruff check --fix app tests
pyrefly check
pytest <narrow-target>
```

CI enforces `ruff format --check`, `ruff check`, `pyrefly check` (strict), and `pytest --cov=app --cov-fail-under=85`. Fix lint/type issues rather than suppressing; `# noqa` or `pyproject.toml` ignores require clear justification.

Judgment rules beyond linters: `docs/llm/app/python-engineering-rules.md`.
