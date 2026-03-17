---
description: "Safely add or update course catalog and graduation requirement data"
name: "Add Course Data"
argument-hint: "Describe the exact data change (course fields, major, credits, and rationale)"
agent: "agent"
---
Update this repository's static academic data for the requested change: **{{input}}**.

Use these project files as the source of truth:
- Course catalog: [`wcc/data/courses.py`](../../wcc/data/courses.py)
- Graduation requirements: [`wcc/data/graduation_requirements.py`](../../wcc/data/graduation_requirements.py)
- Shared models/enums: [`wcc/data/models/`](../../wcc/data/models/)
- CLI behavior that depends on data: [`wcc/commands/grade_report.py`](../../wcc/commands/grade_report.py)
- Project conventions: [`copilot-instructions.md`](../copilot-instructions.md)

Requirements:
1. Apply the request as a **data change first** (avoid logic changes unless absolutely required).
2. Reuse existing enum members (`Major`, `CourseGroup`, `CourseTerm`, `CourseEligibleYear`, `CourseType`) instead of introducing ad-hoc strings.
3. Preserve file style and ordering conventions in the edited data files.
4. If the request is ambiguous or conflicts with existing data, ask a concise follow-up question before editing.

After editing:
- Run `ruff check .`
- Run `pyright .`
- If relevant, validate with `wcc grade-report --help` and related grade-report flows.

Output format:
- Summary of what changed
- Files edited
- Validation results (lint/type-check/CLI)
- Any assumptions or follow-up questions
