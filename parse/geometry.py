from config import TOLERANCE

from .models import XLevel, Area, HorizontalLine, TimeSlot, YLevel


def is_vertical_match(y1: float, y2: float, tolerance: float = TOLERANCE) -> bool:
    """
    Checks if two Y coordinates are located within a specified tolerance.
    """
    return abs(y1 - y2) <= tolerance


def has_horizontal_overlap(a: XLevel, b: XLevel) -> bool:
    """
    Checks if the X coordinates of two objects overlap.
    """
    return (a.x1 < b.x2) and (a.x2 > b.x1)


def is_line_at_bottom(
    area: Area, line: HorizontalLine, tolerance: float = TOLERANCE
) -> bool:
    """
    Checks if a HorizontalLine is located at the bottom (y2) of an Area
    within a specified tolerance.
    """
    if not is_vertical_match(line.y, area.y2, tolerance):
        return False

    return has_horizontal_overlap(XLevel(line.x1, line.x2), XLevel(area.x1, area.x2))


def is_area_below(area1: Area, area2: Area, tolerance: float = TOLERANCE) -> bool:
    """
    Checks if an Area (area1) is located at the bottom (y2) of an Area
    (area2) within a specified tolerance.
    """
    if not is_vertical_match(area1.y1, area2.y2, tolerance):
        return False

    return has_horizontal_overlap(
        XLevel(area1.x1, area1.x2), XLevel(area2.x1, area2.x2)
    )


def get_timeslot_for_area(
    area: Area, timeslot_y_levels: dict[TimeSlot, YLevel]
) -> TimeSlot | None:
    """
    Gets the TimeSlot for an Area. Returns None if no TimeSlot was matched.
    """
    for key in timeslot_y_levels.keys():
        if timeslot_y_levels[key].y1 < area.y2 <= timeslot_y_levels[key].y2:
            return key

    return None
