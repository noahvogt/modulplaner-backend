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
    TimeSlotYLevelsCollectionData,
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


def find_next_cell_below_index(current_area: Area, cells: list[Area]) -> int:
    """
    Returns the index of the first cell directly below current_area, or -1 if none.
    """
    for index, cell in enumerate(cells):
        if is_area_below(cell, current_area):
            return index
    return -1


def get_weekday_from_text(text: str) -> Weekday | None:
    """
    Helper function that tries to get a Weekday from a string.
    Only accepts exact display name matches.
    """
    for weekday in Weekday:
        if weekday.display_name == text:
            return weekday
    return None


def merge_vertically_spanning_cells(
    initial_area: Area,
    remaining_cells: list[Area],
    horizontal_lines: list[HorizontalLine],
    highest_y: float,
    weekday: Weekday,
) -> Area:
    """
    Merges vertically adjacent cells until a bottom boundary (line or page end) is found.
    Mutates remaining_cells by removing used cells.
    Returns the final merged area.
    """
    current_area = initial_area

    while True:
        logging.debug(
            "Searching for bottom boundary of area: %s on %s", current_area, weekday
        )

        # case 1: horizontal line at the bottom of current area?
        if any(
            is_line_at_bottom(current_area, line, tolerance=20)
            for line in horizontal_lines
        ):
            logging.debug("Bottom boundary found: horizontal line")
            return current_area

        # case 2: reached the bottom of the timetable?
        if is_vertical_match(current_area.y2, highest_y):
            logging.debug("Bottom boundary found: highest y level")
            return current_area

        # case 3: find and merge with the next cell below
        next_cell_index = find_next_cell_below_index(current_area, remaining_cells)
        if next_cell_index == -1:
            raise RuntimeError(
                f"No bottom boundary or next cell found for module on {weekday}"
            )

        next_cell = remaining_cells.pop(next_cell_index)
        logging.debug("Vertically merging with cell below: %s", next_cell)

        current_area = Area(
            x1=current_area.x1,
            y1=current_area.y1,
            x2=next_cell.x2,  # use the wider x2 in case of a slight misalignment
            y2=next_cell.y2,
        )


def get_modules_from_weekday(
    weekday: Weekday,
    unmerged_time_entries: UnmergedTimeEntries,
    page: Page,
    timeslot_y_levels: dict[TimeSlot, YLevel],
    page_number: int,
) -> list[RawExtractedModule]:
    """
    Extracts the modules (raw text and start/end) of a weekday on a single pdf page.
    """
    cells = unmerged_time_entries.cells[:]
    horizontal_lines = unmerged_time_entries.horizontal_lines

    highest_y: float = get_highest_y_level(timeslot_y_levels, page_number)
    modules: list[RawExtractedModule] = []
    while cells:
        initial_area = cells.pop(0)

        if is_mostly_white_area(page, initial_area):
            logging.debug("mostly white cell skipped")
            continue

        merged_area: Area = merge_vertically_spanning_cells(
            initial_area, cells, horizontal_lines, highest_y, weekday
        )

        start_timeslot = get_timeslot_for_area(initial_area, timeslot_y_levels)
        if start_timeslot is None:
            raise RuntimeError(
                f"Could not determine start timeslot for module on {weekday}"
            )

        end_timeslot = get_timeslot_for_area(merged_area, timeslot_y_levels)
        if end_timeslot is None:
            raise RuntimeError(
                f"Could not determine end timeslot for merged module on {weekday}"
            )

        text: str = (
            page.crop(
                (merged_area.x1, merged_area.y1, merged_area.x2, merged_area.y2)
            ).extract_text()
            or ""  # do not raise error when extraction returns None for now
        )

        modules.append(
            RawExtractedModule(
                weekday=weekday,
                start_seconds=start_timeslot.start_seconds(),
                end_seconds=end_timeslot.end_seconds(),
                text=text,
                source_page_number=page_number,
            )
        )

    return modules


def get_highest_y_level(timeslot_y_levels, page_number) -> float:
    """
    Gets the highest `YLevel` of all `TimeSlot`'s.

    Raises:
        RuntimeError: If no the highest allowed `TimeSlot` was not mapped to a `YLevel`
    """
    try:
        highest_y_level = timeslot_y_levels[allowed_time_slots[-1]].y2
    except KeyError as e:
        logging.debug("timeslot_y_levels on page %d %s", page_number, timeslot_y_levels)
        raise RuntimeError("Could not get YLevel for latest TimeSlot") from e
    return highest_y_level


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
        timeslot_y_levels: dict[TimeSlot, YLevel] = {}
        unmerged_time_entries_by_weekday: dict[Weekday, UnmergedTimeEntries] = {}
        weekday_areas: dict[Weekday, Area] = init_weekday_areas()

        table: Table = select_main_table(page, page_index)
        text_above_table: str = get_above_table_text(page, table_y1=table.bbox[1])

        collect_weekday_areas_and_timeslot_y_levels(
            weekday_areas, timeslot_y_levels, page, table
        )

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


def collect_weekday_areas_and_timeslot_y_levels(
    weekday_areas: dict[Weekday, Area],
    timeslot_y_levels: dict[TimeSlot, YLevel],
    page: Page,
    table: Table,
) -> None:
    """
    Populates the passed weekday_areas and timeslot_y_levels dicts with the right
    `Area`'s by `Weekday` and `YLevel` by TimeSlot respectively, via side effects.
    """
    expected_timeslot_index = 0
    for row_index, row in enumerate(table.rows):
        if row_index == 0:
            collect_weekday_areas(weekday_areas, page, row, row_index)
        else:
            expected_timeslot_index: int = collect_timeslot_y_levels_of_row(
                timeslot_y_levels,
                TimeSlotYLevelsCollectionData(
                    row_index=row_index,
                    expected_timeslot_index=expected_timeslot_index,
                    last_timeslot=get_last_timeslot(allowed_time_slots),
                    page=page,
                    table=table,
                    weekday_areas=weekday_areas,
                ),
            )


def collect_timeslot_y_levels_of_row(
    timeslot_y_levels: dict[TimeSlot, YLevel],
    collection_data: TimeSlotYLevelsCollectionData,
) -> int:
    """
    Populates the passed and timeslot_y_levels dicts with the right
    `YLevel`'s by `TimeSlot` via side effects.

    Returns:
        int for the current expected `TimeSlot` index
    """
    logging.debug("row: %d, col: %d", collection_data.row_index, 0)
    row = collection_data.table.rows[collection_data.row_index]
    cell = row.cells[0]
    if cell is None:
        logging.warning("None Table cell found, not collecting YLevel of Row")
        return collection_data.expected_timeslot_index
    cell_text = collection_data.page.crop(
        (cell[0], cell[1], cell[2], cell[3])
    ).extract_text()
    target_timeslot = allowed_time_slots[collection_data.expected_timeslot_index]
    if not (
        target_timeslot.start_time in cell_text
        and target_timeslot.end_time in cell_text
    ):
        logging.warning("Unexpected TimeSlot found: '%s'", cell_text)
        return collection_data.expected_timeslot_index
    if target_timeslot == collection_data.last_timeslot:
        for weekday in Weekday:
            new_area = Area(
                x1=collection_data.weekday_areas[weekday].x1,
                y1=collection_data.weekday_areas[weekday].y1,
                x2=collection_data.weekday_areas[weekday].x2,
                y2=cell[3],
            )
            collection_data.weekday_areas[weekday] = new_area
    timeslot_y_levels[target_timeslot] = YLevel(y1=cell[1], y2=cell[3])
    return collection_data.expected_timeslot_index + 1


def collect_weekday_areas(weekday_areas, page, row, row_index) -> None:
    """
    Populates the passed weekday_areas dict with the right
    `Area`'s by `Weekday` via side effects.
    """
    empty_start_found = False
    for column_index, cell in enumerate(row.cells):
        logging.debug("row: %d, col: %d", row_index, column_index)
        logging.debug(cell)
        if cell is None:
            logging.debug("None Table Cell Found")
        else:
            cell_text = page.crop((cell[0], cell[1], cell[2], cell[3])).extract_text()
            if not empty_start_found and len(cell_text) == 0:
                logging.debug("empty start found")
                empty_start_found = True

            weekday_enum: Weekday | None = get_weekday_from_text(cell_text)
            if weekday_enum:
                logging.debug("Weekday %s found", cell_text)
                weekday_areas[weekday_enum] = Area(
                    x1=cell[0], y1=cell[3], x2=cell[2], y2=0
                )


def get_last_timeslot(time_slots: list[TimeSlot]) -> TimeSlot:
    """
    Get the last timeslot a weekday can have.
    """
    if len(time_slots) == 0:
        raise RuntimeError("Cannot get the latest timeslot from an empty list")
    last_timeslot = time_slots[-1]
    logging.debug("last timeslot found: %s", last_timeslot)

    return last_timeslot


def init_weekday_areas() -> dict[Weekday, Area]:
    """
    Initializes the weekday areas with zero-valued `Area`'s for each `Weekday`
    """
    weekday_areas: dict[Weekday, Area] = {}
    for day in Weekday:
        weekday_areas[day] = Area(x1=0, y1=0, x2=0, y2=0)
    return weekday_areas


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
    `UnmergedTimeEntries` by `Weekday` via side effects.
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
    `horizontal_lines` of the `UnmergedTimeEntries` by the passed weekday
    via side effects. These horizontal Lines are timeslot seperator lines.
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
