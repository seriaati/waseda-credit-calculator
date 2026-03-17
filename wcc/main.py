from __future__ import annotations

import csv
import json
import pathlib
from collections import defaultdict
from typing import TYPE_CHECKING

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from wcc.data.courses import COURSES
from wcc.data.graduation_requirements import GRADUATION_REQUIREMENTS
from wcc.data.models import CourseGroup, CourseType
from wcc.data.models.major import Major
from wcc.utils import (
    ADDITIONAL_ELECTIVE_CAPS_BY_MAJOR,
    ADDITIONAL_ELECTIVE_SOURCE_JBSE,
    ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES,
    ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR,
    GRADE_REPORT_PATH,
    GROUP_C_MAJOR_COURSE_GROUPS,
    GradeReportCourse,
    classify_course_group_for_major,
    classify_unmatched_additional_elective_source,
    determine_current_year,
    earned_credits_by_group_for_major,
    is_course_due_by_year,
    is_failed_grade,
    load_grade_report,
    parse_major,
    required_course_completion_status,
    required_course_key,
    resolve_courses,
    show_unknown_courses,
)

if TYPE_CHECKING:
    from wcc.data.models import GraduationRequirement
    from wcc.utils import ResolvedGradeReportCourse

app = typer.Typer()
console = Console()


def _additional_elective_source_labels() -> dict[str, str]:
    return {
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR: "Other major courses (Group C outside selected major)",
        ADDITIONAL_ELECTIVE_SOURCE_JBSE: "JBSE",
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES: "Other faculties",
    }


def _debug_course_attribution_row(
    course: ResolvedGradeReportCourse, major: Major, source_labels: dict[str, str]
) -> tuple[tuple[str, str, str, str, str, str], str | None, int]:
    source_name = str(course.source.get("name", ""))
    grade = str(course.source.get("grade", ""))
    matched = course.matched_course

    if matched is None:
        source = classify_unmatched_additional_elective_source(source_name)
        if source is None:
            row = (
                source_name,
                grade,
                "Unmatched",
                "-",
                "0",
                "Unmatched course; not counted in category totals",
            )
            return row, None, 0

        row = (
            source_name,
            grade,
            CourseGroup.E.value,
            CourseGroup.E.value,
            str(course.earned_credits),
            (
                "Unmatched but treated as Additional Electives "
                f"({source_labels[source]}) before caps"
            ),
        )
        return row, source, course.earned_credits

    grouped_as = classify_course_group_for_major(matched, major)
    if grouped_as == CourseGroup.E and matched.group in GROUP_C_MAJOR_COURSE_GROUPS:
        row = (
            source_name,
            grade,
            grouped_as.value,
            CourseGroup.E.value,
            str(course.earned_credits),
            (
                "Group C course outside selected major; counted as Additional Electives "
                "(other major courses) before caps"
            ),
        )
        return row, ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR, course.earned_credits

    row = (
        source_name,
        grade,
        grouped_as.value,
        grouped_as.value,
        str(course.earned_credits),
        f"Counted in {grouped_as.value}",
    )
    return row, None, 0


def _build_missing_categories_debug_rows(
    resolved_courses: list[ResolvedGradeReportCourse], major: Major
) -> tuple[list[tuple[str, str, str, str, str, str]], dict[str, int]]:
    source_labels = _additional_elective_source_labels()
    additional_source_attempted: dict[str, int] = defaultdict(int)
    course_debug_rows: list[tuple[str, str, str, str, str, str]] = []

    for course in resolved_courses:
        row, source, counted_credits = _debug_course_attribution_row(course, major, source_labels)
        course_debug_rows.append(row)
        if source is not None:
            additional_source_attempted[source] += counted_credits

    return course_debug_rows, additional_source_attempted


def _print_missing_categories_debug(
    course_debug_rows: list[tuple[str, str, str, str, str, str]],
    additional_source_attempted: dict[str, int],
    category_debug_rows: list[tuple[str, str, str, str, str, str]],
    major: Major,
) -> None:
    course_debug_table = Table(
        title="Debug: Course Attribution",
        show_header=True,
        header_style="bold yellow",
        show_lines=True,
    )
    course_debug_table.add_column("Course", style="bold")
    course_debug_table.add_column("Grade", justify="center")
    course_debug_table.add_column("Classified As", style="magenta")
    course_debug_table.add_column("Counted In", style="cyan")
    course_debug_table.add_column("Counted Credits", justify="right", style="green")
    course_debug_table.add_column("Reason")

    for row in course_debug_rows:
        course_debug_table.add_row(*row)
    console.print(course_debug_table)

    additional_caps_table = Table(
        title="Debug: Additional Electives Caps", show_header=True, header_style="bold yellow"
    )
    additional_caps_table.add_column("Source", style="bold")
    additional_caps_table.add_column("Before Cap", justify="right", style="cyan")
    additional_caps_table.add_column("Cap", justify="right", style="magenta")
    additional_caps_table.add_column("Counted", justify="right", style="green")

    source_labels = _additional_elective_source_labels()
    caps = ADDITIONAL_ELECTIVE_CAPS_BY_MAJOR[major]
    for source in (
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR,
        ADDITIONAL_ELECTIVE_SOURCE_JBSE,
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES,
    ):
        before_cap = additional_source_attempted.get(source, 0)
        cap = caps[source]
        counted = before_cap if cap is None else min(before_cap, cap)
        cap_display = "No cap" if cap is None else str(cap)
        additional_caps_table.add_row(
            source_labels[source], str(before_cap), cap_display, str(counted)
        )

    console.print(additional_caps_table)

    category_debug_table = Table(
        title="Debug: Category Calculation", show_header=True, header_style="bold yellow"
    )
    category_debug_table.add_column("Category", style="bold")
    category_debug_table.add_column("Base Earned", justify="right", style="green")
    category_debug_table.add_column("Shared Added", justify="right", style="cyan")
    category_debug_table.add_column("Shared From", style="magenta")
    category_debug_table.add_column("Required", justify="right", style="cyan")
    category_debug_table.add_column("Missing", justify="right", style="red")

    for row in category_debug_rows:
        category_debug_table.add_row(*row)
    console.print(category_debug_table)


def _build_missing_category_totals(
    graduation_requirement: GraduationRequirement,
    earned_credits_by_group: dict[CourseGroup, int],
    debug: bool,
) -> tuple[list[tuple[str, str, str, str]], int, list[tuple[str, str, str, str, str, str]]]:
    display_rows: list[tuple[str, str, str, str]] = []
    category_debug_rows: list[tuple[str, str, str, str, str, str]] = []
    total_missing = 0

    for group, required_credit in graduation_requirement.minimum_credits.items():
        required = int(required_credit)
        base_earned = earned_credits_by_group[group]
        shared_earned = 0
        earned = base_earned
        if required_credit.shared_with is not None:
            shared_earned = earned_credits_by_group[required_credit.shared_with]
            earned += shared_earned

        missing = max(0, required - earned)
        total_missing += missing
        display_rows.append((group.value, str(earned), str(required), str(missing)))

        if debug:
            shared_from = required_credit.shared_with.value if required_credit.shared_with else "-"
            category_debug_rows.append(
                (
                    group.value,
                    str(base_earned),
                    str(shared_earned),
                    shared_from,
                    str(required),
                    str(missing),
                )
            )

    return display_rows, total_missing, category_debug_rows


@app.command()
def load() -> None:
    """Loads a grade report from a CSV file and save the parsed courses to a JSON file."""
    courses: list[GradeReportCourse] = []

    major = questionary.select("Select major:", choices=[major.value for major in Major]).ask()
    year = questionary.select(
        "Select what year you are in:", choices=["1st Year", "2nd Year", "3rd Year", "4th Year"]
    ).ask()
    csv_path = questionary.path("Select grade report CSV file:").ask()

    try:
        with pathlib.Path(csv_path).open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError as e:
        typer.echo(f"File not found: {csv_path}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Error reading file: {e}")
        raise typer.Exit(code=1) from e

    for row in rows:
        if not row["operationboxf 4"]:
            continue

        try:
            course = GradeReportCourse.from_csv_row(row)
        except ValueError as e:
            typer.echo(f"Error parsing row: {row}")
            typer.echo(str(e))
            continue
        courses.append(course)

    data = {"major": major, "year": year, "courses": [course.__dict__ for course in courses]}

    try:
        GRADE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        typer.echo(f"Error creating grade report directory: {e}")
        raise typer.Exit(code=1) from e

    try:
        with GRADE_REPORT_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        typer.echo(f"Error saving grade report: {e}")
        raise typer.Exit(code=1) from e

    typer.echo(f"Grade report saved to {GRADE_REPORT_PATH.resolve()}.")


@app.command()
def total() -> None:
    """Displays total credits earned so far."""
    data = load_grade_report()
    resolved_courses, unknown_courses = resolve_courses(data)

    attempted_credits = sum(int(course.source.get("credits", 0)) for course in resolved_courses)
    earned_credits = sum(course.earned_credits for course in resolved_courses)
    failed_count = sum(
        1 for course in resolved_courses if is_failed_grade(str(course.source.get("grade", "")))
    )
    passed_count = len(resolved_courses) - failed_count

    table = Table(title="Credit Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Courses in report", str(len(resolved_courses)))
    table.add_row("Passed courses", f"[green]{passed_count}[/green]")
    table.add_row("Failed courses", f"[red]{failed_count}[/red]")
    table.add_row("Attempted credits", str(attempted_credits))
    table.add_row("Earned credits (F = 0)", f"[bold green]{earned_credits}[/bold green]")

    console.print(Panel.fit(table, border_style="cyan"))
    show_unknown_courses(unknown_courses)


@app.command("missing-categories")
def missing_categories(
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show detailed course-by-course calculation used for missing category totals.",
    ),
) -> None:
    """Displays missing credits in each graduation requirement category."""
    data = load_grade_report()

    major = parse_major(str(data.get("major", "")))
    if major is None:
        typer.echo("Major is missing or unsupported in the grade report.")
        raise typer.Exit(code=1)

    graduation_requirement = GRADUATION_REQUIREMENTS.get(major)
    if graduation_requirement is None:
        typer.echo(f"No graduation requirement data found for major: {major.value}")
        raise typer.Exit(code=1)

    resolved_courses, unknown_courses = resolve_courses(data)
    earned_credits_by_group = earned_credits_by_group_for_major(resolved_courses, major)

    course_debug_rows: list[tuple[str, str, str, str, str, str]]
    additional_source_attempted: dict[str, int]
    if debug:
        course_debug_rows, additional_source_attempted = _build_missing_categories_debug_rows(
            resolved_courses, major
        )
    else:
        course_debug_rows, additional_source_attempted = [], {}

    table = Table(
        title=f"Missing Credits by Category ({major.value})",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Category", style="bold")
    table.add_column("Earned", justify="right", style="green")
    table.add_column("Required", justify="right", style="cyan")
    table.add_column("Missing", justify="right", style="red")

    display_rows, total_missing, category_debug_rows = _build_missing_category_totals(
        graduation_requirement, earned_credits_by_group, debug
    )
    for row in display_rows:
        table.add_row(*row)

    console.print(table)
    console.print(
        Panel.fit(
            f"[bold red]Total missing credits:[/bold red] {total_missing}", border_style="red"
        )
    )

    if debug:
        _print_missing_categories_debug(
            course_debug_rows=course_debug_rows,
            additional_source_attempted=additional_source_attempted,
            category_debug_rows=category_debug_rows,
            major=major,
        )

    show_unknown_courses(unknown_courses)


@app.command("missing-required")
def missing_required() -> None:
    """Displays required courses not yet completed, considering major and current year."""
    data = load_grade_report()

    major = parse_major(str(data.get("major", "")))
    if major is None:
        typer.echo("Major is missing or unsupported in the grade report.")
        raise typer.Exit(code=1)

    current_year = determine_current_year(data)

    resolved_courses, unknown_courses = resolve_courses(data)
    passed_required_course_keys, failed_required_course_keys = required_course_completion_status(
        resolved_courses, major
    )

    due_required_courses = [
        course
        for course in COURSES
        if course.type is not None
        and course.type.get(major) == CourseType.REQUIRED
        and is_course_due_by_year(course, current_year)
    ]

    missing_rows: list[tuple[str, str, str, str]] = []
    for course in due_required_courses:
        course_key = required_course_key(course.name)
        if course_key in passed_required_course_keys:
            continue

        status = "[yellow]Not taken[/yellow]"
        if course_key in failed_required_course_keys:
            status = "[red]Failed (retake needed)[/red]"

        missing_rows.append((course.name, course.group.value, course.term.value, status))

    if not missing_rows:
        console.print(
            Panel.fit(
                f"[bold green]Nice![/bold green] No required courses due by year {current_year} are currently missing.",
                border_style="green",
            )
        )
        show_unknown_courses(unknown_courses)
        return

    table = Table(
        title=f"Missing Required Courses (Year {current_year} • {major.value})",
        show_header=True,
        header_style="bold blue",
        show_lines=True,
    )
    table.add_column("Course", style="bold")
    table.add_column("Category", style="magenta")
    table.add_column("Term", style="cyan")
    table.add_column("Status", style="bold")

    for row in missing_rows:
        table.add_row(*row)

    console.print(table)
    console.print(
        Panel.fit(
            f"[bold red]Required courses still missing:[/bold red] {len(missing_rows)}",
            border_style="red",
        )
    )
    show_unknown_courses(unknown_courses)


@app.command("failed")
def failed() -> None:
    """Displays all courses the student has failed (grade F)."""
    data = load_grade_report()
    resolved_courses, _ = resolve_courses(data)

    failed_courses = [
        course
        for course in resolved_courses
        if is_failed_grade(str(course.source.get("grade", "")))
    ]

    if not failed_courses:
        console.print(
            Panel.fit("[bold green]No failed courses found.[/bold green]", border_style="green")
        )
        return

    table = Table(
        title="Failed Courses", show_header=True, header_style="bold red", show_lines=True
    )
    table.add_column("Course", style="bold")
    table.add_column("Year", style="cyan")
    table.add_column("Term", style="cyan")
    table.add_column("Credits", justify="right", style="yellow")
    table.add_column("Grade", justify="center", style="red")

    for course in failed_courses:
        src = course.source
        table.add_row(
            str(src.get("name", "")),
            str(src.get("year", "")),
            str(src.get("term", "")),
            str(src.get("credits", "")),
            str(src.get("grade", "")),
        )

    console.print(table)
    console.print(
        Panel.fit(
            f"[bold red]Total failed courses:[/bold red] {len(failed_courses)}", border_style="red"
        )
    )


@app.command()
def overview() -> None:
    """Displays all courses organized by category in a formatted table with grades and credits."""
    data = load_grade_report()
    major = parse_major(str(data.get("major", "")))
    resolved_courses, unknown_courses = resolve_courses(data)

    courses_by_group = defaultdict(list)
    for course in resolved_courses:
        group = "Unrecognized"
        if course.matched_course is not None:
            group = (
                course.matched_course.group.value
                if major is None
                else classify_course_group_for_major(course.matched_course, major).value
            )
        courses_by_group[group].append(course)

    totals = [0, 0]  # [attempted, earned]
    for group_name in sorted(courses_by_group.keys()):
        courses = courses_by_group[group_name]
        attempted = sum(int(c.source.get("credits", 0)) for c in courses)
        earned = sum(c.earned_credits for c in courses)
        totals[0] += attempted
        totals[1] += earned

        table = Table(
            title=group_name, show_header=True, header_style="bold cyan", show_lines=False
        )
        table.add_column("Course", style="bold", no_wrap=False)
        table.add_column("Year", justify="center", style="cyan")
        table.add_column("Term", justify="center", style="cyan")
        table.add_column("Grade", justify="center")
        table.add_column("Credits", justify="right", style="yellow")
        table.add_column("Earned", justify="right", style="green")

        for course in courses:
            src = course.source
            color = "red" if is_failed_grade(str(src.get("grade", ""))) else "green"
            table.add_row(
                str(src.get("name", "")),
                str(src.get("year", "")),
                str(src.get("term", "")),
                f"[{color}]{src.get('grade', '')}[/{color}]",
                str(src.get("credits", "")),
                str(course.earned_credits),
            )

        pct = 100 * earned // attempted if attempted > 0 else 0
        console.print(table)
        console.print(f"  [cyan]Credits:[/cyan] {earned}/{attempted} ({pct}% completion)\n")

    pct_total = 100 * totals[1] // totals[0] if totals[0] > 0 else 0
    console.print(
        Panel.fit(
            f"[bold cyan]Total Earned:[/bold cyan] {totals[1]}/{totals[0]} credits "
            f"([bold green]{pct_total}%[/bold green] completion)",
            border_style="cyan",
        )
    )
    show_unknown_courses(unknown_courses)


if __name__ == "__main__":
    app()
