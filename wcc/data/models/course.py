from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wcc.data.models.major import Major


class CourseGroup(StrEnum):
    A1 = "Humanities and Social Sciences"
    A2_1 = "English for Science and Engineering"
    A2_2 = "English as a Second Language"
    A2_3 = "Japanese"
    A2_4 = "Languages other than English or Japanese"

    B1 = "Core Mathematics"
    B2_1 = "Core Physics"
    B2_2 = "Core Chemistry"
    B2_3 = "Core Bioscience"
    B3 = "Core Laboratory"
    B4 = "Core Computer Science"

    C_1 = "Required"
    C_2 = "Restricted Elective"
    C_3 = "Elective"

    D = "Physical Education / Independent Study"

    E = "Additional Electives"


class CourseTerm(StrEnum):
    SPRING = "Spring Semester"
    FALL = "Fall Semester"

    SPRING_Q = "Spring Quarter"
    SUMMER_Q = "Summer Quarter"
    FALL_Q = "Fall Quarter"
    WINTER_Q = "Winter Quarter"

    V = "Varies by course"
    INT = "Intensive Course"


class CourseEligibleYear(StrEnum):
    APR_1 = "April Enrollees, 1st Year"
    APR_2 = "April Enrollees, 2nd Year"
    APR_3 = "April Enrollees, 3rd Year"
    APR_4 = "April Enrollees, 4th Year"

    SEP_1 = "September Enrollees, 1st Year"
    SEP_2 = "September Enrollees, 2nd Year"
    SEP_3 = "September Enrollees, 3rd Year"
    SEP_4 = "September Enrollees, 4th Year"


class CourseType(StrEnum):
    REQUIRED = "Required"
    RESTRICTED_ELECTIVE = "Restricted Elective"
    ELECTIVE = "Elective"


@dataclass
class Course:
    name: str
    group: CourseGroup
    credits: int
    term: CourseTerm
    eligible_years: Sequence[CourseEligibleYear]
    type: dict[Major, CourseType] | None = None
