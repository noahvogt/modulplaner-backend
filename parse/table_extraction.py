import logging
from multiprocessing import Pool
from pathlib import Path

from pdfplumber.page import Page
from pdfplumber.table import Table
import pdfplumber

from config import (
    CLASS_TIMETABLE_PDF_TABLE_SETTINGS,
    ALLOWED_TIMESLOTS,
    CLASS_TIMETABLE_PDF_MIN_DIMENSIONS,
)
from .models import (
    Weekday,
    TimeSlot,
    YLevel,
    RawExtractedModule,
    UnmergedTimeEntries,
    Area,
    HorizontalLine,
    ClassPdfExtractionPageData,
    RawClassPdfExtractionPageData,
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
    TimeSlot(start_time=timeslot_tuple[0], end_time=timeslot_tuple[1])
    for timeslot_tuple in ALLOWED_TIMESLOTS
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
                area = Area(
                    x1=area.x1, y1=area.y1, x2=matched_area.x2, y2=matched_area.y2
                )

        text = page.crop((area.x1, area.y1, area.x2, area.y2)).extract_text()
        timeslot = get_timeslot_for_area(area, timeslot_y_levels)
        if timeslot is None:
            raise RuntimeError("Could not match TimeSlot to Cell Area")
        end_seconds = timeslot.end_seconds()
        modules.append(
            RawExtractedModule(
                weekday=weekday,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                text=text,
                source_page_number=page_number,
            )
        )
    return modules


def get_usable_table_index(found_tables: list) -> int:
    """
    Identifies the index of the timetable on the page based on dimensions.

    Raises:
        RuntimeError: If no or multiple tables matching the minimum dimensions are found.
    """
    if not found_tables:
        raise RuntimeError("No matching tables found.")

    valid_indices = []
    for index, table in enumerate(found_tables):
        x0, top, x1, bottom = table.bbox
        width = x1 - x0
        height = bottom - top
        logging.debug(
            "table num %d: width: %d, height: %d",
            index + 1,
            width,
            height,
        )
        if (
            width >= CLASS_TIMETABLE_PDF_MIN_DIMENSIONS
            and height >= CLASS_TIMETABLE_PDF_MIN_DIMENSIONS
        ):
            valid_indices.append(index)

    if len(valid_indices) > 1:
        raise RuntimeError(
            f"Found {len(valid_indices)} valid tables, expected at most 1. "
            "Ambiguous table selection."
        )

    if len(valid_indices) == 1:
        return valid_indices[0]

    return 0


def process_page(
    input_filename: Path, page_index: int
) -> RawClassPdfExtractionPageData:
    """
    Process a single page of the PDF to extract modules and header text.
    Designed to be run in a separate process.
    """
    with pdfplumber.open(input_filename) as pdf:
        page = pdf.pages[page_index]
        weekday_areas: dict[Weekday, Area] = {}
        timeslot_y_levels: dict[TimeSlot, YLevel] = {}
        unmerged_time_entries_by_weekday: dict[Weekday, UnmergedTimeEntries] = {}

        for day in Weekday:
            weekday_areas[day] = Area(x1=0, y1=0, x2=0, y2=0)

        table: Table = select_main_table(page, page_index)
        text_above_table = get_above_table_text(page, table_y1=table.bbox[1])

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
                                x1=cell[0], y1=cell[3], x2=cell[2], y2=0
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
                        logging.warning("Unexpected Timeslot found: '%s'", cell_text)
                    else:
                        # assumes this is the last timeslot ever
                        if target_timeslot == TimeSlot(
                            start_time="20:30", end_time="21:15"
                        ):
                            for weekday in Weekday:
                                new_area = Area(
                                    x1=weekday_areas[weekday].x1,
                                    y1=weekday_areas[weekday].y1,
                                    x2=weekday_areas[weekday].x2,
                                    y2=cell[3],
                                )
                                weekday_areas[weekday] = new_area
                        timeslot_y_levels[target_timeslot] = YLevel(
                            y1=cell[1], y2=cell[3]
                        )
                        expected_timeslot_index += 1

        collected_unmerged_time_entries_by_weekday(
            unmerged_time_entries_by_weekday, weekday_areas, table, page
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
        return RawClassPdfExtractionPageData(
            raw_extracted_modules=all_modules, above_table_text=text_above_table
        )

def select_main_table(page: Page, page_index: int) -> Table:
    """
    Selects the main table on the PDF Page. This should be the timetable.
    """
    found_tables = page.find_tables(CLASS_TIMETABLE_PDF_TABLE_SETTINGS)
    logging.debug(
        "amount of tables found on page %d: %d",
        page_index + 1,
        len(found_tables),
    )
    table = found_tables[get_usable_table_index(found_tables)]
    return table


def collected_unmerged_time_entries_by_weekday(
    unmerged_time_entries_by_weekday: dict[Weekday, UnmergedTimeEntries],
    weekday_areas: dict[Weekday, Area],
    table: Table,
    page: Page,
) -> None:
    """
    Populates the passed unmerged_time_entries_by_weekday dict with the
    `UnmergedTimeEntries` by `Weekday`.
    """
    for weekday in Weekday:
        unmerged_time_entries_by_weekday[weekday] = UnmergedTimeEntries(
            cells=[], horizontal_lines=[]
        )
        target_area: Area = weekday_areas[weekday]
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
                    unmerged_time_entries_by_weekday[weekday].cells.append(
                        Area(x1=cell[0], y1=cell[1], x2=cell[2], y2=cell[3])
                    )
                    logging.debug("%s cell found", weekday)

        collect_horizontal_lines(
            unmerged_time_entries_by_weekday, page, target_area, weekday
        )


def collect_horizontal_lines(
    unmerged_time_entries_by_weekday: dict[Weekday, UnmergedTimeEntries],
    page: Page,
    target_area: Area,
    weekday: Weekday,
) -> None:
    """
    Populates the passed unmerged_time_entries_by_weekday dict with the
    `horizontal_lines` of the `UnmergedTimeEntries` by the passed weekday.
    These horizontal Lines are timeslot seperator lines.
    """
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
            unmerged_time_entries_by_weekday[weekday].horizontal_lines.append(
                HorizontalLine(x1=line_x1, x2=line_x2, y=line_bottom)
            )


def extract_data_from_class_pdf(
    input_filename: Path, num_of_jobs: int = 1
) -> list[ClassPdfExtractionPageData]:
    """
    Extracts all data from the specified Class Timetable PDF filename.
    Can run via multiple jobs.
    """
    logging.info("Starting extraction with %d jobs", num_of_jobs)

    num_pages: int = get_number_of_pdf_pages(input_filename)
    logging.info("Found %d pages to process", num_pages)

    processed_pages: list[RawClassPdfExtractionPageData] = process_pages_in_parallel(
        num_of_jobs, input_filename, num_pages
    )

    extraction_data: list[ClassPdfExtractionPageData] = process_metadata_sequentially(
        processed_pages
    )

    return extraction_data


def process_metadata_sequentially(
    processed_pages: list[RawClassPdfExtractionPageData],
) -> list[ClassPdfExtractionPageData]:
    """
    Process the above table text into `PageMetadata`'s of the processed pages.
    """
    extraction_data: list[ClassPdfExtractionPageData] = []
    previous_page_metadata: list[PageMetadata] = []

    for processed_page in processed_pages:
        page_metadata = parse_above_table_text(
            processed_page.above_table_text, previous_page_metadata
        )
        previous_page_metadata.append(page_metadata)
        extraction_data.append(
            ClassPdfExtractionPageData(
                raw_extracted_modules=processed_page.raw_extracted_modules,
                page_metadata=page_metadata,
            )
        )
    return extraction_data


def process_pages_in_parallel(
    num_of_jobs: int, input_filename: Path, num_of_pages: int
) -> list[RawClassPdfExtractionPageData]:
    """Extracts the pdf pages in parallel based on the number of jobs"""
    with Pool(processes=num_of_jobs) as pool:
        results = pool.starmap(
            process_page, [(input_filename, i) for i in range(num_of_pages)]
        )
    return results


def get_number_of_pdf_pages(input_filename: Path) -> int:
    """Get the number of pdf pages using the pdfplumber library"""
    with pdfplumber.open(input_filename) as pdf:
        num_pages = len(pdf.pages)
    return num_pages


def get_above_table_text(page: Page, table_y1: float) -> str:
    """
    Get the text above the timetable for metadata parsing
    """
    upper_region = page.crop((0, 0, page.width, table_y1))
    text_above_table = upper_region.extract_text()

    logging.debug("Text found above the table:")
    logging.debug(text_above_table)

    return text_above_table
