import logging
from pdfplumber.page import Page
import pdfplumber

from config import TABLE_SETTINGS, ALLOWED_TIMESLOTS
from .models import (
    Weekday,
    TimeSlot,
    YLevel,
    RawExtractedModule,
    UnmergedTimeEntries,
    Area,
    HorizontalLine,
    ClassPdfExtractionPageData,
    PageMetadata,
)
from .above_table_text import parse_above_table_text
from .geometry import (
    get_timeslot_for_area,
    is_line_at_bottom,
    is_area_below,
    is_vertical_match,
)
from .img import is_mostly_white_area

allowed_time_slots: list[TimeSlot] = [
    TimeSlot(*timeslot_tuple) for timeslot_tuple in ALLOWED_TIMESLOTS
]


def get_weekday_from_text(text: str) -> Weekday | None:
    """
    Helper function that tries to get a Weekday from a string.
    Only accepts exact display name matches.
    """
    for weekday in Weekday:
        if weekday.display_name == text:
            return weekday
    return None


def get_modules_from_weekday(
    weekday: Weekday,
    unmerged_time_entries: UnmergedTimeEntries,
    page: Page,
    timeslot_y_levels: dict[TimeSlot, YLevel],
    page_number: int,
) -> list[RawExtractedModule]:
    """
    Extracts the modules (raw text and start/end) of a weekday on a single pdf page
    """
    highest_y_level = timeslot_y_levels[allowed_time_slots[-1]].y2
    modules = []
    while len(unmerged_time_entries.cells) > 0:
        area = unmerged_time_entries.cells.pop(0)
        if is_mostly_white_area(page, area):
            logging.debug("mostly white cell skipped")
            continue
        timeslot = get_timeslot_for_area(area, timeslot_y_levels)
        if timeslot is None:
            raise RuntimeError("Could not match TimeSlot to Cell Area")
        start_seconds = timeslot.start_seconds()
        line_at_bottom_found = False
        while not line_at_bottom_found:
            logging.debug("searching for line at bottom of: %s", area)
            logging.debug("line candidates:")
            for line in unmerged_time_entries.horizontal_lines:
                logging.debug("testing horizontal line: %s", line)
                if is_line_at_bottom(area, line, tolerance=20):
                    line_at_bottom_found = True
                    logging.debug("candidate line found")
                    break
            else:

                if is_vertical_match(area.y2, highest_y_level):
                    logging.debug("highest y level matched")
                    break
                found_matching_next_cell_index = -1
                for index, potential_cell_below in enumerate(
                    unmerged_time_entries.cells
                ):
                    if is_area_below(potential_cell_below, area):
                        found_matching_next_cell_index = index
                        break
                else:
                    raise RuntimeError(
                        f"No matching cell below found to merge with on {weekday}"
                    )
                logging.debug("vertically merging cells for %s", weekday)
                matched_area = unmerged_time_entries.cells.pop(
                    found_matching_next_cell_index
                )
                logging.debug("matched cell area: %s", matched_area)
                area = Area(area.x1, area.y1, matched_area.x2, matched_area.y2)

        text = page.crop((area.x1, area.y1, area.x2, area.y2)).extract_text()
        timeslot = get_timeslot_for_area(area, timeslot_y_levels)
        if timeslot is None:
            raise RuntimeError("Could not match TimeSlot to Cell Area")
        end_seconds = timeslot.end_seconds()
        modules.append(
            RawExtractedModule(weekday, start_seconds, end_seconds, text, page_number)
        )
    return modules


def extract_data_from_class_pdf(
    input_filename: str, lecturers_file=None
) -> list[ClassPdfExtractionPageData]:
    """
    Extracts all data from class timetable pdf's
    """
    extraction_data: list[ClassPdfExtractionPageData] = []
    previous_page_metadata: list[PageMetadata] = []
    unmerged_time_entries_by_weekday: dict[Weekday, UnmergedTimeEntries] = {}
    with pdfplumber.open(input_filename) as pdf:
        for page_index, page in enumerate(pdf.pages):
            weekday_areas: dict[Weekday, Area] = {}
            timeslot_y_levels: dict[TimeSlot, YLevel] = {}
            for day in Weekday:
                weekday_areas[day] = Area(0, 0, 0, 0)

            found_tables = page.find_tables(TABLE_SETTINGS)
            logging.debug(
                "amount of tables found on page %d: %d",
                page_index + 1,
                len(found_tables),
            )
            table = found_tables[0]
            table_y1 = table.bbox[1]
            text_above_table = get_above_table_text(page, table_y1)

            empty_start_found = False

            # get weekday and timeslot areas
            expected_timeslot_index = 0
            for row_index, row in enumerate(table.rows):
                if row_index == 0:
                    for column_index, cell in enumerate(row.cells):
                        logging.debug("row: %d, col: %d", row_index, column_index)
                        logging.debug(cell)
                        if cell is None:
                            logging.debug("None Table Cell Found")
                        else:
                            cell_text = page.crop(
                                (cell[0], cell[1], cell[2], cell[3])
                            ).extract_text()
                            if not empty_start_found and len(cell_text) == 0:
                                logging.debug("empty start found")
                                empty_start_found = True

                            weekday_enum = get_weekday_from_text(cell_text)
                            if weekday_enum:
                                logging.debug("Weekday %s found", cell_text)
                                weekday_areas[weekday_enum] = Area(
                                    cell[0], cell[3], cell[2], 0
                                )
                else:
                    logging.debug("row: %d, col: %d", row_index, 0)
                    cell = row.cells[0]
                    if cell is None:
                        logging.warning("Unexpected None Table Cell Found")
                    else:
                        cell_text = page.crop(
                            (cell[0], cell[1], cell[2], cell[3])
                        ).extract_text()
                        target_timeslot = allowed_time_slots[expected_timeslot_index]
                        if not (
                            target_timeslot.start_time in cell_text
                            and target_timeslot.end_time in cell_text
                        ):
                            logging.warning(
                                "Unexpected Timeslot found: '%s'", cell_text
                            )
                        else:
                            # assumes this is the last timeslot ever
                            if target_timeslot == TimeSlot("20:30", "21:15"):
                                for weekday in Weekday:
                                    new_area = Area(
                                        weekday_areas[weekday].x1,
                                        weekday_areas[weekday].y1,
                                        weekday_areas[weekday].x2,
                                        cell[3],
                                    )
                                    weekday_areas[weekday] = new_area
                            timeslot_y_levels[target_timeslot] = YLevel(
                                cell[1], cell[3]
                            )
                            expected_timeslot_index += 1

            for weekday in Weekday:
                unmerged_time_entries_by_weekday[weekday] = UnmergedTimeEntries([], [])
                target_area = weekday_areas[weekday]
                logging.debug("target_area: %s", target_area)

                for row_index, row in enumerate(table.rows):
                    for column_index, cell in enumerate(row.cells):
                        if cell is None:
                            logging.debug("None table cell found")
                            continue
                        logging.debug("row: %d, col: %d", row_index, column_index)
                        logging.debug("cell: %s", cell)
                        if (
                            target_area.x1 <= cell[0]
                            and target_area.y1 <= cell[1]
                            and target_area.x2 >= cell[2]
                            and target_area.y2 >= cell[3]
                        ):
                            cell_dimensions = cell[0], cell[1], cell[2], cell[3]
                            unmerged_time_entries_by_weekday[weekday].cells.append(
                                Area(*cell_dimensions)
                            )
                            logging.debug("%s cell found", weekday)

                for line_found in page.lines:
                    line_x1 = line_found["x0"]
                    line_x2 = line_found["x1"]
                    line_y1 = line_found["y0"]
                    line_y2 = line_found["y1"]
                    line_bottom = line_found["bottom"]

                    # ignore non horizontal lines
                    if line_y1 != line_y2:
                        continue

                    if target_area.x1 <= line_x1 and target_area.x2 >= line_x2:
                        logging.debug("%s timeslot seperator line found", weekday)
                        unmerged_time_entries_by_weekday[
                            weekday
                        ].horizontal_lines.append(
                            HorizontalLine(line_x1, line_x2, line_bottom)
                        )

            all_modules: list[RawExtractedModule] = []
            for weekday in Weekday:
                all_modules.extend(
                    get_modules_from_weekday(
                        weekday,
                        unmerged_time_entries_by_weekday[weekday],
                        page,
                        timeslot_y_levels,
                        page_index + 1,
                    )
                )
            page_metadata = parse_above_table_text(
                text_above_table, previous_page_metadata
            )
            previous_page_metadata.append(page_metadata)
            extraction_data.append(
                ClassPdfExtractionPageData(all_modules, page_metadata)
            )
        return extraction_data


def get_above_table_text(page: Page, table_y1: float) -> str:
    """
    Get the text above the timetable for metadata parsing
    """
    upper_region = page.crop((0, 0, page.width, table_y1))
    text_above_table = upper_region.extract_text()

    logging.debug("Text found above the table:")
    logging.debug(text_above_table)

    return text_above_table
