from wcc.data.models import CourseGroup, GraduationCredit, GraduationRequirement, Major

GRADUATION_REQUIREMENTS = {
    Major.FSE_CSCE: GraduationRequirement(
        major=Major.FSE_CSCE,
        minimum_credits={
            CourseGroup.A1: GraduationCredit(10),
            CourseGroup.A2_1: GraduationCredit(2),
            CourseGroup.A2_2: GraduationCredit(0),
            CourseGroup.A2_3: GraduationCredit(4, shared_with=CourseGroup.A2_4),
            CourseGroup.A2_4: GraduationCredit(0),
            CourseGroup.B1: GraduationCredit(12),
            CourseGroup.B2_1: GraduationCredit(6),
            CourseGroup.B2_2: GraduationCredit(0),
            CourseGroup.B2_3: GraduationCredit(0),
            CourseGroup.B3: GraduationCredit(2),
            CourseGroup.B4: GraduationCredit(6),
            CourseGroup.C_1: GraduationCredit(22),
            CourseGroup.C_2: GraduationCredit(38),
            CourseGroup.C_3: GraduationCredit(4),
            CourseGroup.D: GraduationCredit(0),
            CourseGroup.E: GraduationCredit(20),
        },
    )
}
