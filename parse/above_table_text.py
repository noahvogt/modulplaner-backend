from re import search
import logging

from .models import (
    PageMetadata,
    SemesterType,
    Semester,
    ExportTimestamp,
    DegreeProgram,
    Date,
    Time,
)


def parse_above_table_text(
    txt: str, previous_page_metadata: list[PageMetadata]
) -> PageMetadata:
    lines = txt.split("\n")
    if len(lines) != 3:
        raise RuntimeError("Invalid Number of Lines.")

    semester_type: SemesterType = get_semester_value(lines[0])
    semester: Semester = Semester(
        yyyy=get_semester_year(lines[0]), semester_type=semester_type
    )
    class_name: str = get_class_name(lines[2])
    degree_program: DegreeProgram = get_degree_program(
        lines[2], class_name, previous_page_metadata
    )
    export_timestamp: ExportTimestamp = get_export_timestamp(lines[1])

    return PageMetadata(
        semester=semester,
        export_timestamp=export_timestamp,
        class_name=class_name,
        degree_program=degree_program,
    )


def get_export_timestamp(second_line: str) -> ExportTimestamp:
    line_length = len(second_line)

    match = search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", second_line)

    if match:
        date_dd, date_mm, date_yyyy = [int(entry) for entry in match.groups()]
    else:
        raise RuntimeError("Could not find date for timestamp extraction")

    for index, char in enumerate(second_line):
        if char == ":" and index - 2 >= 0 and index + 2 < line_length:
            try:
                time_hh = int(second_line[index - 2 : index])
                time_mm = int(second_line[index + 1 : index + 3])
                break
            except (TypeError, ValueError) as e:
                raise RuntimeError("Timestamp Extraction failed") from e
    else:
        raise RuntimeError("No Time found")

    return ExportTimestamp(
        date=Date(yyyy=date_yyyy, mm=date_mm, dd=date_dd),
        time=Time(hh=time_hh, mm=time_mm),
    )


def get_class_name(third_line: str) -> str:
    first_space_index = third_line.find(" ")
    if first_space_index == -1:
        raise RuntimeError("No space character found in third line")
    if len(third_line) > 2 and third_line[0:2] == "- ":
        return third_line[2:]
    return third_line[0:first_space_index]


def get_degree_program(
    third_line: str, class_name: str, previous_page_metadata: list[PageMetadata]
) -> DegreeProgram:
    logging.debug("class_name: '%s'", class_name)
    if "Kontext BWL" and "Kommunikation" and "GSW" in third_line:
        return DegreeProgram.MIXED_BWL_GSW_KOMM
    for degree_program in DegreeProgram:
        if degree_program.value in third_line:
            return degree_program
    logging.warning("Using heuristics to guess the degree_program in %s", third_line)
    try:
        for page_metadata in previous_page_metadata:
            if page_metadata.class_name == class_name[:-1]:
                return page_metadata.degree_program
        if class_name[-1] == class_name[-2]:
            for page_metadata in previous_page_metadata:
                if class_name[:-2] in page_metadata.class_name:
                    return page_metadata.degree_program
    except IndexError:
        pass

    try:
        if class_name[1] == "D":
            return DegreeProgram.DATASCIENCE
        if class_name[1] == "I":
            return DegreeProgram.INFORMATIK
        if class_name[1:3] == "iC":
            return DegreeProgram.ICOMPETENCE

        if class_name == "alle" or class_name[1:4] == "MSE":
            return DegreeProgram.AGNOSTIC
    except IndexError:
        pass

    raise RuntimeError(f"No Valid DegreeProgram found in line {third_line}")


def get_semester_value(first_line: str) -> SemesterType:
    if SemesterType.FS.value in first_line and SemesterType.HS.value not in first_line:
        return SemesterType.FS
    if SemesterType.HS.value in first_line and SemesterType.FS.value not in first_line:
        return SemesterType.HS
    raise RuntimeError("Could not determine SemesterType")


def get_semester_year(first_line: str) -> int:
    numeric_char_count = 0
    for index, char in enumerate(first_line):
        if char.isdigit():
            numeric_char_count += 1
            if numeric_char_count == 4:
                return int(first_line[index - 4 : index + 1])
        else:
            numeric_char_count = 0
    raise RuntimeError("Could not determine Semester year (yyyy)")
