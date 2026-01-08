#!/usr/bin/env python3

import logging
from argparse import ArgumentParser
import json
from pydantic import TypeAdapter

from parse import (
    extract_data_from_class_pdf,
    get_modules_for_class_json,
    get_modules_json,
    get_classes,
    deduplicate_modules,
    ClassPdfExtractionPageData,
    ClassJsonModule,
)

from config import CLASS_TIMETABLE_PDF_INPUT_FILE, CLASSES_JSON_OUTPUT_FILE

logger = logging.getLogger("modulplaner-backend")


def get_valid_lecturers(file_path: str) -> list[str]:
    """
    Reads the lecturers JSON file and extracts a list of valid lecturer shorthands.
    """
    valid_lecturers: list[str] = []
    try:
        logger.warning("reading lecturers file: '%s'", file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "short" in entry:
                        valid_lecturers.append(entry["short"])
        logger.info(
            "Loaded %d valid lecturers from %s", len(valid_lecturers), file_path
        )
    except Exception as e:
        logger.error("Failed to load valid lecturers from '%s': %s", file_path, e)
    return valid_lecturers


def main() -> None:
    parser = ArgumentParser(description="Parse Class Timetable PDF to JSON.")
    parser.add_argument(
        "-l",
        "--lecturers",
        help="Path to the lecturers.json file (Optional)",
        default=None,
    )
    parser.add_argument(
        "-i",
        "--input",
        help="Path to the input Class Timetable PDF file",
        default=CLASS_TIMETABLE_PDF_INPUT_FILE,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output JSON file",
        default=CLASSES_JSON_OUTPUT_FILE,
    )
    parser.add_argument(
        "--save-intermediate",
        help="Path to save the intermediate extraction data (JSON format) and exit",
        default=None,
    )
    parser.add_argument(
        "--load-intermediate",
        help="Path to load the intermediate extraction data from (JSON format) and skip extraction",
        default=None,
    )
    parser.add_argument(
        "-j",
        "--jobs",
        help="Number of parallel jobs to use for extraction (default: 1)",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--log-level",
        help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        default="INFO",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    args = parser.parse_args()
    lecturers_file = args.lecturers

    logging.basicConfig(level=args.log_level)

    valid_lecturer_shorthands: list[str] | None = None
    if lecturers_file:
        valid_lecturer_shorthands = get_valid_lecturers(lecturers_file)

    extraction_data: list[ClassPdfExtractionPageData]

    if args.load_intermediate:
        logger.info("Loading intermediate data from %s", args.load_intermediate)
        with open(args.load_intermediate, "r", encoding="utf-8") as f:
            extraction_data = TypeAdapter(
                list[ClassPdfExtractionPageData]
            ).validate_json(f.read())
    else:
        extraction_data = extract_data_from_class_pdf(args.input, num_of_jobs=args.jobs)
        if args.save_intermediate:
            logger.info("Saving intermediate data to %s", args.save_intermediate)
            with open(args.save_intermediate, "w", encoding="utf-8") as f:
                f.write(
                    TypeAdapter(list[ClassPdfExtractionPageData])
                    .dump_json(extraction_data)
                    .decode("utf-8")
                )
            return

    parsed_modules: list[ClassJsonModule] = [
        module
        for data in extraction_data
        for module in get_modules_for_class_json(
            data.raw_extracted_modules,
            data.page_metadata.class_name,
            data.page_metadata.degree_program,
            get_classes(extraction_data),
            valid_lecturer_shorthands,
        )
    ]
    parsed_modules = deduplicate_modules(parsed_modules)
    json_output: str = get_modules_json(parsed_modules)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(json_output)


if __name__ == "__main__":
    main()
