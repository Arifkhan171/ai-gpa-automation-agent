"""
AcadTrack — Grade Letter Utility
University of Loralai, Pakistan

HEC Pakistan grading scale.
"""


def get_grade_letter(gp: float) -> str:
    """
    Convert a grade point (0.0 – 4.0) to its HEC Pakistan letter grade.

    >= 4.00 → "A"
    >= 3.70 → "A-"
    >= 3.30 → "B+"
    >= 3.00 → "B"
    >= 2.70 → "B-"
    >= 2.30 → "C+"
    >= 2.00 → "C"
    >= 1.70 → "C-"
    >= 1.00 → "D"
    <  1.00 → "F"
    """
    if gp >= 4.00:
        return "A"
    elif gp >= 3.70:
        return "A-"
    elif gp >= 3.30:
        return "B+"
    elif gp >= 3.00:
        return "B"
    elif gp >= 2.70:
        return "B-"
    elif gp >= 2.30:
        return "C+"
    elif gp >= 2.00:
        return "C"
    elif gp >= 1.70:
        return "C-"
    elif gp >= 1.00:
        return "D"
    else:
        return "F"
