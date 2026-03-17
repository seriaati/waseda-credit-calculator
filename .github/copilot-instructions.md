# Project Guidelines

## Code Style
- Target Python version is **3.14+** (`pyproject.toml`, `ruff.toml`).
- Keep type hints explicit; this project uses pyright in `standard` mode.
- Follow existing lint/format settings in `ruff.toml` (line length 100, `future-annotations = true`).
- Prefer `@dataclass` and `StrEnum` patterns already used in `wcc/data/models/`.
- Preserve current import style and `TYPE_CHECKING` guards to avoid runtime circular imports.

## Architecture
- CLI entrypoint: `wcc/main.py` (Typer app).
- Command logic: `wcc/commands/grade_report.py` (load/total/missing-categories/missing-required).
- Static domain data:
  - `wcc/data/courses.py` for course catalog (`COURSES` tuple)
  - `wcc/data/graduation_requirements.py` for requirement rules (`GRADUATION_REQUIREMENTS`)
  - `wcc/data/models/` for shared model/enums
- Grade report JSON files are read/written under `.wcc/grade_reports/`.

## Build and Test
- Run CLI: `uv run wcc/main.py --help`
- Lint: `ruff check .`
- Type-check: `pyright .`
- There is currently no automated test suite configured; validate behavior via CLI flows.

## Conventions
- `StrEnum` values are user-facing labels; comparisons should use enum members where possible (not ad-hoc strings).
- In grade-report processing, failed grades (`"F"`) count as zero earned credits.
- Course matching intentionally normalizes names (brackets/parentheses/colon variants) in `wcc/commands/grade_report.py`; preserve this behavior when changing matching logic.
- Use `typer.Exit(code=1)` for user-facing command failures instead of uncaught exceptions.

## Pitfalls
- `README.md` is currently empty; prefer deriving behavior from code and `--help` output.
- Paths under `.wcc/grade_reports` are relative to current working directory; avoid silently changing path semantics.
- Updates to course catalog or graduation requirements should be treated as data changes first, logic changes second.
