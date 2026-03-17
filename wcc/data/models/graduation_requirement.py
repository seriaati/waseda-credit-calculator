from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from . import CourseGroup, Major


class GraduationCredit:
    def __init__(self, value: int, *, shared_with: CourseGroup | None = None) -> None:
        if value < 0:
            msg = "Graduation credit cannot be negative."
            raise ValueError(msg)

        self.value = value
        self.shared_with = shared_with

    def __int__(self) -> int:
        return self.value


@dataclass
class GraduationRequirement:
    major: Major
    minimum_credits: dict[CourseGroup, GraduationCredit]
    intake: Literal["sep", "apr"] = "sep"

    @property
    def total_minimum_credits(self) -> int:
        return sum(int(credit) for credit in self.minimum_credits.values())
