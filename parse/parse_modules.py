import logging
from typing import List

from pydantic import TypeAdapter

from config import LECTURER_SHORTHAND_SIZE

from .models import (
    RawExtractedModule,
    ClassJsonModule,
    ParsedModuleCellTextData,
    DegreeProgram,
    TeachingType,
    Weekday,
    StartsWithMatch,
    ClassPdfExtractionPageData,
)

logger = logging.getLogger("modulplaner-backend.parse_modules")


def get_modules_for_class_json(
    modules: list[RawExtractedModule],
    class_name: str,
    degree_program: DegreeProgram,
    all_class_names: list[str],
    valid_lecturer_shorthands: list[str] | None = None,
) -> list[ClassJsonModule]:
    """
    Parses the Raw Extracted Modules from the Class Timetable PDF into the format to
    export them to the classes.json file.
    """
    output_modules: list[ClassJsonModule] = []

    for input_module in modules:
        parsed_data: ParsedModuleCellTextData = parse_module_class_pdf_cell_text(
            input_module.text,
            class_name,
            degree_program,
            all_class_names,
            valid_lecturer_shorthands,
        )

        output_modules.append(
            ClassJsonModule(
                weekday=input_module.weekday,
                module_shorthand=parsed_data.module_shorthand,  # pyright: ignore
                start_seconds=input_module.start_seconds,  # pyright: ignore
                end_seconds=input_module.end_seconds,  # pyright: ignore
                degree_program=parsed_data.degree_program,  # pyright: ignore
                class_name=class_name,  # pyright: ignore
                rooms=parsed_data.rooms,
                pages=[input_module.source_page_number],
                part_of_other_classes=parsed_data.part_of_other_classes,
                teaching_type=parsed_data.teaching_type,
                lecturer_shorthands=parsed_data.lecturer_shorthands,  # pyright: ignore
                id=get_id(
                    class_name,
                    parsed_data.module_shorthand,
                    input_module.weekday,
                    input_module.start_seconds,
                    input_module.end_seconds,
                ),
            )
        )

    return output_modules


def deduplicate_modules(modules: list[ClassJsonModule]) -> list[ClassJsonModule]:
    """de-duplicate modules based on their id field"""
    unique_modules_map: dict[str, ClassJsonModule] = {}
    for module in modules:
        if module.id in unique_modules_map:
            existing_module = unique_modules_map[module.id]
            existing_module.pages = sorted(
                list(set(existing_module.pages + module.pages))
            )
        else:
            unique_modules_map[module.id] = module
    return list(unique_modules_map.values())


def get_modules_json(modules: List[ClassJsonModule]) -> str:
    """
    Serializes a list of ClassJsonModule objects into a formatted JSON string.
    """
    adapter = TypeAdapter(List[ClassJsonModule])
    return adapter.dump_json(modules, by_alias=True).decode("utf-8")


def parse_mixed_degree_programs(
    degree_program: DegreeProgram, module_shorthand: str
) -> DegreeProgram:
    if degree_program == DegreeProgram.MIXED_BWL_GSW_KOMM:
        if module_shorthand in ["bplan", "lean"]:
            return DegreeProgram.KONTEXT_BWL
        if module_shorthand in ["wisa", "aua"]:
            return DegreeProgram.KONTEXT_KOMM
        return DegreeProgram.KONTEXT_GSW
    return degree_program


def parse_module_class_pdf_cell_text(
    text: str,
    class_name: str,
    degree_program: DegreeProgram,
    all_class_names: list[str],
    valid_lecturer_shorthands: list[str] | None = None,
) -> ParsedModuleCellTextData:
    """
    Parse a single Class Timetable PDF module cell text.
    """
    lines = text.split("\n")
    logger.debug("Parsing module cell text: \n%s", text)
    if len(lines) != 3 and len(lines) != 2:
        raise RuntimeError("Invalid Number of Lines in the cell text.")
    if len(lines) == 3:
        rooms = get_rooms(lines[2])
        teaching_type = get_teaching_type(lines[2])
    else:
        rooms = []
        teaching_type = TeachingType.ON_SITE

    module_shorthand = get_module_shorthand(lines[0], class_name, all_class_names)

    return ParsedModuleCellTextData(
        module_shorthand=module_shorthand,
        degree_program=parse_mixed_degree_programs(degree_program, module_shorthand),
        class_name=class_name,
        rooms=rooms,
        part_of_other_classes=[],
        teaching_type=teaching_type,
        lecturer_shorthands=get_lecturer_shorthands(
            lines[1], valid_lecturer_shorthands
        ),
    )


def get_lecturer_shorthands(
    second_line: str, valid_lecturer_shorthands: list[str] | None = None
) -> list[str]:
    """
    Get the Lecturer Shorthand based on the second Class Timetable PDF cell line.
    You can provide a list of valid lecturer shorthands for more accurate parsing.
    """
    lecturer_shorthands: list[str] = []
    words = second_line.split(" ")
    if valid_lecturer_shorthands is None:
        for word in words:
            if len(word) == LECTURER_SHORTHAND_SIZE:
                lecturer_shorthands.append(word)
            else:
                logger.warning("Could not get Lecturer Shorthand from word: %s", word)
    else:
        for word in words:
            exact_starts_with_match = matches_startswith(
                word, valid_lecturer_shorthands
            )
            minus_last_char_starts_with_match = matches_startswith(
                word[:-1], valid_lecturer_shorthands
            )

            if word in valid_lecturer_shorthands:
                lecturer_shorthands.append(word)
            elif is_valid_starts_with_match(exact_starts_with_match):
                lecturer_shorthands.append(exact_starts_with_match.shorthand_found)
            elif is_valid_starts_with_match(minus_last_char_starts_with_match):
                lecturer_shorthands.append(
                    minus_last_char_starts_with_match.shorthand_found
                )
            else:
                logger.warning("Could not get Lecturer Shorthand from word: %s", word)
    return lecturer_shorthands


def is_valid_starts_with_match(exact_starts_with_match: StartsWithMatch) -> bool:
    return (
        exact_starts_with_match.shorthand_found != ""
        and exact_starts_with_match.num_of_matches == 1
    )


def matches_startswith(
    word: str, valid_lecturer_shorthands: list[str]
) -> StartsWithMatch:
    shorthand_with_start: str = ""
    # catch the number of matches to make sure the matching is unambiguous
    num_of_startwith_matches: int = 0
    for shorthand in valid_lecturer_shorthands:
        if shorthand.startswith(word):
            shorthand_with_start = shorthand
            num_of_startwith_matches += 1
    return StartsWithMatch(
        shorthand_found=shorthand_with_start, num_of_matches=num_of_startwith_matches
    )


def get_module_shorthand(
    first_line: str, class_name: str, all_class_names: list[str]
) -> str:
    """
    Get the Module Shorthand based on the first Class Timetable PDF cell line.
    """
    words = first_line.split(" ")
    if len(words) < 1:
        raise RuntimeError("Cannot extract Module Shorthand")
    word = words[0]
    if len(words) == 1:
        for i in reversed(range(len(class_name) + 1)):
            class_name_part = class_name[0:i]
            if word.endswith(class_name_part):
                word = word[: word.rfind(class_name_part)]
                debug_msg = (
                    f"cut off class name part '{class_name_part}'"
                    + f" of class name '{class_name}' in line '{first_line}'"
                )
                logger.debug(debug_msg)
                break

        for foreign_class_name in all_class_names:
            if word.endswith(foreign_class_name):
                word = word[: word.rfind(foreign_class_name)]
                logger.debug(
                    "cut off class name '%s' in line '%s'",
                    foreign_class_name,
                    first_line,
                )
                break
    if len(word) == 0:
        raise RuntimeError("Module Shorthand cannot be empty")
    return word


def get_id(
    class_name: str,
    module_shorthand: str,
    weekday: Weekday,
    start_seconds: int,
    end_seconds: int,
) -> str:
    """Calculate the json id of a module."""
    return (
        f"{class_name}-{module_shorthand}-{weekday.index}-{start_seconds}-{end_seconds}"
    )


def get_teaching_type(third_line: str) -> TeachingType:
    """
    Get the teaching type based on the third Class Timetable PDF cell line.
    """
    if "Online" in third_line:
        return TeachingType.ONLINE
    return TeachingType.ON_SITE


def get_rooms(third_line: str) -> list[str]:
    """
    Get the rooms based on the third Class Timetable PDF cell line.
    """
    if "DSMixe" in third_line:
        return []

    words = third_line.split(" ")
    return words


def get_classes(extraction_data: list[ClassPdfExtractionPageData]) -> list[str]:
    """
    Get the classes from the class page's metadata.
    """
    return [page_data.page_metadata.class_name for page_data in extraction_data]
