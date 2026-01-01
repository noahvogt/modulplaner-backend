#!/usr/bin/env python3

import logging

from parse import (
    extract_data_from_class_pdf,
    get_modules_for_class_json,
    get_modules_json,
    ClassPdfExtractionPageData,
    ClassJsonModule,
)

from config import CLASS_PDF_INPUT_FILE, CLASSES_JSON_OUTPUT_FILE


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)
    extraction_data: list[ClassPdfExtractionPageData] = extract_data_from_class_pdf(
        CLASS_PDF_INPUT_FILE
    )
    parsed_modules: list[ClassJsonModule] = [
        module
        for data in extraction_data
        for module in get_modules_for_class_json(
            data.raw_extracted_modules,
            data.page_metadata.class_name,
            data.page_metadata.degree_program,
        )
    ]
    json: str = get_modules_json(parsed_modules)

    with open(CLASSES_JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(json)


if __name__ == "__main__":
    main()
