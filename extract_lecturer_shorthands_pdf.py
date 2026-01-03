#!/usr/bin/env python3

import logging
from argparse import ArgumentParser

import pdfplumber
from pdfplumber.table import Table
from pydantic import TypeAdapter

from config import (
    LECTURER_SHORTHAND_PDF_TABLE_SETTINGS,
    LECTURER_SHORTHAND_PDF_PDF_INPUT_FILE,
    LECTURER_SHORTHAND_JSON_OUTPUT_FILE,
)
from parse import RawLecturer, Lecturer


def extract_rows_from_lecturer_shorthand_pdf(input_file) -> list[RawLecturer]:
    lecturers: list[RawLecturer] = []

    with pdfplumber.open(input_file) as pdf:
        # find the X coordinates of "Nachname" and "Vorname" on the first page
        # to use as fixed separators for all rows. This assumes they do not
        # deviate their x values on subsequent pages.
        first_page = pdf.pages[0]
        nachname_rects = first_page.search("Nachname")
        vorname_rects = first_page.search("Vorname")

        sep_x_1 = 0
        sep_x_2 = 0

        if nachname_rects and vorname_rects:
            # Subtract 2 pixels to ensure the start of the letter is caught
            # even if it drifts slightly left.
            sep_x_1 = nachname_rects[0]["x0"] - 2
            sep_x_2 = vorname_rects[0]["x0"] - 2
            logging.debug(
                "calculated separators: %d (Nachname), %d (Vorname)", sep_x_1, sep_x_2
            )
        else:
            raise RuntimeError("Could not find headers for separator calculation")

        lines_y1: list = []
        min_line_y1 = 0
        max_line_y1 = 0

        for page_index, page in enumerate(pdf.pages):
            # Remove top header and bottom footer based on first / last line.
            # Assumes the header and footer positions do not go beyond these
            # values on subsequent pages.
            if page_index == 0:
                for line in page.lines:
                    lines_y1.append(line.get("y1"))
                if lines_y1:
                    min_line_y1 = min(lines_y1)
                    max_line_y1 = max(lines_y1)

            # guard against empty lines list if page has no lines
            if not lines_y1:
                logging.warning("First page has no lines")
                crop_box = (0, 0, page.width, page.height)
            else:
                crop_box = (0, min_line_y1, page.width, max_line_y1)

            cropped_page = page.crop(crop_box)

            found_tables: list[Table] = cropped_page.find_tables(
                LECTURER_SHORTHAND_PDF_TABLE_SETTINGS
            )

            if len(found_tables) != 1:
                raise RuntimeError(
                    "Did not find exactly 1 table in the lecuturer shorthands pdf"
                    + f" on page {page_index + 1}"
                )

            table: Table = found_tables[0]

            for row_index, row in enumerate(table.rows):
                if row is None:
                    logging.debug("None table row found")
                    continue

                valid_cells = [cell for cell in row.cells if cell is not None]

                if not valid_cells:
                    continue

                row_top = valid_cells[0][1]
                row_bottom = valid_cells[0][3]
                row_left = valid_cells[0][0]
                row_right = valid_cells[-1][2]

                row_bbox = (row_left, row_top, row_right, row_bottom)

                logging.debug("row %d dimensions: %s", row_index, row_bbox)

                # column 1: From start of row -> Nachname separator
                col1_bbox = (row_left, row_top, sep_x_1, row_bottom)
                # column 2: From Nachname separator -> Vorname separator
                col2_bbox = (sep_x_1, row_top, sep_x_2, row_bottom)
                # column 3: From Vorname separator -> End of row
                col3_bbox = (sep_x_2, row_top, row_right, row_bottom)

                logging.debug("col 1 bbox: %s", col1_bbox)
                logging.debug("col 2 bbox: %s", col2_bbox)
                logging.debug("col 3 bbox: %s", col3_bbox)

                row_text: str = cropped_page.crop(row_bbox).extract_text()
                logging.debug("row text: %s", row_text)
                col1_text = cropped_page.crop(col1_bbox).extract_text()
                logging.debug("col 1 text: %s", col1_text)
                col2_text = cropped_page.crop(col2_bbox).extract_text()
                logging.debug("col 2 text: %s", col2_text)
                col3_text = cropped_page.crop(col3_bbox).extract_text()
                logging.debug("col 3 text: %s", col3_text)
                lecturers.append(RawLecturer(col1_text, col3_text, col2_text))

    return lecturers


def is_table_header_row(raw_lecturer: RawLecturer) -> bool:
    return (
        raw_lecturer.shorthand == "Name"
        and raw_lecturer.surname == "Nachname"
        and raw_lecturer.firstname == "Vorname"
    )


def is_vak_example_row(raw_lecturer):
    return (
        raw_lecturer.shorthand == "vak"
        and raw_lecturer.surname == ""
        and raw_lecturer.firstname == ""
    )


def get_lecturers_json(modules: list[Lecturer]) -> str:
    """
    Serializes a list of Lecturer objects into a formatted JSON string.
    """
    adapter = TypeAdapter(list[Lecturer])
    return adapter.dump_json(modules).decode("utf-8")


def parse_lecturers(raw_lecturers: list[RawLecturer]) -> list[Lecturer]:
    lecturers: list[Lecturer] = []
    for raw_lecturer in raw_lecturers:
        if is_table_header_row(raw_lecturer) or is_vak_example_row(raw_lecturer):
            logging.debug("skipping raw lecturer: %s", raw_lecturer)
        else:
            new_lecturer: Lecturer = Lecturer(
                short=raw_lecturer.shorthand,
                surname=raw_lecturer.surname,
                firstname=raw_lecturer.firstname,
            )
            if new_lecturer in lecturers:
                logging.debug("skipped over duplicate lecturer: %s", new_lecturer)
            else:
                lecturers.append(new_lecturer)
    return lecturers


def main() -> None:
    parser = ArgumentParser(description="Parse lecturer shorthand PDF to JSON.")
    parser.add_argument(
        "-i",
        "--input",
        help="Path to the input PDF file",
        default=LECTURER_SHORTHAND_PDF_PDF_INPUT_FILE,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output JSON file",
        default=LECTURER_SHORTHAND_JSON_OUTPUT_FILE,
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    raw_lecturers: list[RawLecturer] = extract_rows_from_lecturer_shorthand_pdf(
        args.input
    )
    lecturers: list[Lecturer] = parse_lecturers(raw_lecturers)
    json_output: str = get_lecturers_json(lecturers)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(json_output)


if __name__ == "__main__":
    main()
