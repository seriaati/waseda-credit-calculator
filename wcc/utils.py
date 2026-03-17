from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Self

import questionary
import typer
from rich.console import Console
from rich.table import Table

from wcc.data.courses import COURSES
from wcc.data.models import Course, CourseEligibleYear, CourseGroup, CourseTerm, CourseType
from wcc.data.models.major import Major

GRADE_REPORT_PATH = pathlib.Path(".wcc/grade_report.json")
FAILED_GRADES = {"F"}
console = Console()

GROUP_C_MAJOR_COURSE_GROUPS = frozenset({CourseGroup.C_1, CourseGroup.C_2, CourseGroup.C_3})

ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR = "other_major_courses"
ADDITIONAL_ELECTIVE_SOURCE_JBSE = "other_courses_jbse"
ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES = "other_courses_other_faculties"

ADDITIONAL_ELECTIVE_CAPS_BY_MAJOR: dict[Major, dict[str, int | None]] = {
    Major.FSE_MS: {
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR: None,
        ADDITIONAL_ELECTIVE_SOURCE_JBSE: 4,
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES: 4,
    },
    Major.FSE_CSCE: {
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR: None,
        ADDITIONAL_ELECTIVE_SOURCE_JBSE: 8,
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES: 4,
    },
    Major.FSE_ME: {
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR: None,
        ADDITIONAL_ELECTIVE_SOURCE_JBSE: 16,
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES: 16,
    },
    Major.FSE_CEE: {
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR: None,
        ADDITIONAL_ELECTIVE_SOURCE_JBSE: 8,
        ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES: 8,
    },
}


@dataclass
class GradeReportCourse:
    name: str
    year: str
    term: str
    credits: int
    grade: str

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        return cls(
            name=row["operationboxf"],
            year=row["operationboxf 2"],
            term=row["operationboxf 3"],
            credits=int(row["operationboxf 4"]),
            grade=row["operationboxf 5"],
        )


@dataclass
class ResolvedGradeReportCourse:
    source: dict[str, Any]
    matched_course: Course | None
    earned_credits: int


def normalize_course_name(name: str) -> str:
    cleaned = re.sub(r"\[[^\]]*\]", "", name)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def course_name_candidates(name: str) -> list[str]:
    candidates: list[str] = []

    def add(candidate: str) -> None:
        normalized = normalize_course_name(candidate)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    base = normalize_course_name(name)
    add(base)
    if ":" in base:
        add(base.split(":", maxsplit=1)[0])

    current = base
    while True:
        trimmed = re.sub(r"\s*\([^()]*\)\s*$", "", current)
        if trimmed == current or not trimmed:
            break

        add(trimmed)
        if ":" in trimmed:
            add(trimmed.split(":", maxsplit=1)[0])
        current = trimmed

    return candidates


def build_course_index() -> dict[str, Course]:
    return {normalize_course_name(course.name): course for course in COURSES}


def find_course_by_name(name: str) -> Course | None:
    index = build_course_index()
    for candidate in course_name_candidates(name):
        if candidate in index:
            return index[candidate]
    return None


def is_japanese_language_center_course(name: str) -> bool:
    lowered_name = name.lower()
    return (
        "center of japanese language" in lowered_name
        or "center for japanese language" in lowered_name
    )


def japanese_language_center_course(name: str, course_credits: int) -> Course:
    return Course(
        name=name,
        group=CourseGroup.A2_3,
        credits=course_credits,
        term=CourseTerm.V,
        eligible_years=(CourseEligibleYear.APR_1, CourseEligibleYear.SEP_1),
    )


def is_failed_grade(grade: str) -> bool:
    return grade.strip().upper() in FAILED_GRADES


def required_course_key(course_name: str) -> str:
    base = normalize_course_name(course_name)
    return re.sub(r"\s*\(\d+\)\s*$", "", base).strip()


def load_grade_report() -> dict[str, Any]:
    try:
        with GRADE_REPORT_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        typer.echo("No grade report found. Run 'wcc load' first.")
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Error reading grade report: {e}")
        raise typer.Exit(code=1) from e


def resolve_courses(data: dict[str, Any]) -> tuple[list[ResolvedGradeReportCourse], list[str]]:
    resolved_courses: list[ResolvedGradeReportCourse] = []
    unknown_courses: list[str] = []

    for raw_course in data.get("courses", []):
        course_credits = int(raw_course.get("credits", 0))
        grade = str(raw_course.get("grade", ""))
        earned_credits = 0 if is_failed_grade(grade) else course_credits

        course_name = str(raw_course.get("name", ""))
        matched_course = find_course_by_name(course_name)
        if matched_course is None and is_japanese_language_center_course(course_name):
            matched_course = japanese_language_center_course(course_name, course_credits)

        if matched_course is None:
            unknown_courses.append(course_name)

        resolved_courses.append(
            ResolvedGradeReportCourse(
                source=raw_course, matched_course=matched_course, earned_credits=earned_credits
            )
        )

    return resolved_courses, unknown_courses


def parse_major(major: str) -> Major | None:
    try:
        return Major(major)
    except ValueError:
        return None


def parse_year(year_text: str) -> int | None:
    mapping = {"1st Year": 1, "2nd Year": 2, "3rd Year": 3, "4th Year": 4}
    return mapping.get(year_text)


def eligible_year_number(eligible_year: CourseEligibleYear) -> int:
    return int(eligible_year.name.split("_")[1])


def is_course_due_by_year(course: Course, current_year: int) -> bool:
    earliest_eligible_year = min(eligible_year_number(y) for y in course.eligible_years)
    return earliest_eligible_year <= current_year


def determine_current_year(data: dict[str, Any]) -> int:
    current_year = parse_year(str(data.get("year", "")))
    if current_year is not None:
        return current_year

    year_text = questionary.select(
        "Select what year you are in:", choices=["1st Year", "2nd Year", "3rd Year", "4th Year"]
    ).ask()
    current_year = parse_year(str(year_text))
    if current_year is None:
        typer.echo("Unable to determine your current year.")
        raise typer.Exit(code=1)
    return current_year


def required_course_completion_status(
    resolved_courses: list[ResolvedGradeReportCourse], major: Major
) -> tuple[set[str], set[str]]:
    passed_required_course_keys: set[str] = set()
    failed_required_course_keys: set[str] = set()

    for course in resolved_courses:
        matched_course = course.matched_course
        if matched_course is None or matched_course.type is None:
            continue
        if matched_course.type.get(major) != CourseType.REQUIRED:
            continue

        course_key = required_course_key(matched_course.name)
        if course.earned_credits > 0:
            passed_required_course_keys.add(course_key)
            failed_required_course_keys.discard(course_key)
        elif course_key not in passed_required_course_keys:
            failed_required_course_keys.add(course_key)

    return passed_required_course_keys, failed_required_course_keys


def classify_course_group_for_major(course: Course, major: Major) -> CourseGroup:
    # Group C courses offered by other majors must be treated as "Other major courses" and
    # counted in Additional Electives (Table 1), not in the student's own C_1/C_2/C_3 buckets.
    if course.group in GROUP_C_MAJOR_COURSE_GROUPS and (
        course.type is None or major not in course.type
    ):
        return CourseGroup.E

    # All group B courses marked as ELECTIVE course according to the major count toward Group E
    if (
        course.group.name.startswith("B")
        and course.type
        and course.type.get(major) == CourseType.ELECTIVE
    ):
        return CourseGroup.E

    # B4 courses marked as REQUIRED count toward Group C_1
    if (
        course.group == CourseGroup.B4
        and course.type
        and course.type.get(major) == CourseType.REQUIRED
    ):
        return CourseGroup.C_1

    return course.group


def classify_unmatched_additional_elective_source(course_name: str) -> str | None:
    lowered_name = course_name.lower()

    if "jbse" in lowered_name:
        return ADDITIONAL_ELECTIVE_SOURCE_JBSE

    if any(
        marker in lowered_name
        for marker in (
            "global education center",
            "center for international education",
            "center for japanese language",
        )
    ):
        if "mathematics" in lowered_name:
            return None
        return ADDITIONAL_ELECTIVE_SOURCE_OTHER_FACULTIES

    return None


def earned_credits_by_group_for_major(
    resolved_courses: list[ResolvedGradeReportCourse], major: Major
) -> dict[CourseGroup, int]:
    earned_by_group: dict[CourseGroup, int] = defaultdict(int)
    additional_elective_credits_by_source: dict[str, int] = {}

    # Track credits for Intro programming courses (B4 restricted electives)
    b4_intro_credits = 0

    for course in resolved_courses:
        matched_course = course.matched_course
        if matched_course is None:
            source = classify_unmatched_additional_elective_source(
                str(course.source.get("name", ""))
            )
            if source is not None:
                additional_elective_credits_by_source[source] = (
                    additional_elective_credits_by_source.get(source, 0) + course.earned_credits
                )
            continue

        grouped_as = classify_course_group_for_major(matched_course, major)
        if grouped_as == CourseGroup.E and matched_course.group in GROUP_C_MAJOR_COURSE_GROUPS:
            additional_elective_credits_by_source[ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR] = (
                additional_elective_credits_by_source.get(ADDITIONAL_ELECTIVE_SOURCE_OTHER_MAJOR, 0)
                + course.earned_credits
            )
            continue

        # Rule: students are required to earn 2 credits from one of Introduction to C, Introduction to Java,
        # or Introduction to Fortran. If they earn more than 2 credits from these courses,
        # the excess WILL NOT be counted toward graduation.
        if (
            matched_course.group == CourseGroup.B4
            and matched_course.name.startswith("Introduction to ")
            and "Programming" in matched_course.name
        ):
            if b4_intro_credits < 2:
                allowed_credits = min(course.earned_credits, 2 - b4_intro_credits)
                b4_intro_credits += course.earned_credits
                earned_by_group[grouped_as] = earned_by_group.get(grouped_as, 0) + allowed_credits
            else:
                b4_intro_credits += course.earned_credits
            continue

        earned_by_group[grouped_as] = earned_by_group.get(grouped_as, 0) + course.earned_credits

    caps = ADDITIONAL_ELECTIVE_CAPS_BY_MAJOR[major]
    for source, earned in additional_elective_credits_by_source.items():
        cap = caps[source]
        earned_by_group[CourseGroup.E] = earned_by_group.get(CourseGroup.E, 0) + (
            earned if cap is None else min(earned, cap)
        )

    return earned_by_group


def show_unknown_courses(unknown_courses: list[str]) -> None:
    if not unknown_courses:
        return

    table = Table(title="Courses not found in internal course database", show_lines=True)
    table.add_column("Course Name", style="yellow")

    for name in sorted(set(unknown_courses)):
        table.add_row(name)

    console.print(table)
    console.print(
        "[yellow]These courses were not matched in the internal course database; some may still be treated as Additional Electives based on course name rules.[/yellow]"
    )
