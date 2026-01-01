from typing import List
import logging

from pydantic import TypeAdapter

from config import LECTURER_SHORTHAND_SIZE

from .models import (
    RawExtractedModule,
    ClassJsonModule,
    ParsedModuleCellTextData,
    DegreeProgram,
    TeachingType,
    Weekday,
)


def get_modules_for_class_json(
    modules: list[RawExtractedModule], class_name: str, degree_program: DegreeProgram
) -> list[ClassJsonModule]:
    output_modules: list[ClassJsonModule] = []

    for input_module in modules:
        parsed_data: ParsedModuleCellTextData = parse_module_cell_text(
            input_module.text, class_name, degree_program
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
                lecturer_shorthands=parsed_data.lecturer_shortnames,  # pyright: ignore
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


def parse_module_cell_text(
    text: str, class_name: str, degree_program: DegreeProgram
) -> ParsedModuleCellTextData:
    lines = text.split("\n")
    logging.debug("Parsing module cell text: \n%s", text)
    if len(lines) != 3 and len(lines) != 2:
        raise RuntimeError("Invalid Number of Lines in the cell text.")
    if len(lines) == 3:
        rooms = get_rooms(lines[2])
        teaching_type = get_teaching_type(lines[2])
    else:
        rooms = []
        teaching_type = TeachingType.ON_SITE

    module_shorthand = get_module_shorthand(lines[0], class_name)

    return ParsedModuleCellTextData(
        module_shorthand=module_shorthand,
        degree_program=parse_mixed_degree_programs(degree_program, module_shorthand),
        class_name=class_name,
        rooms=rooms,
        part_of_other_classes=[],
        teaching_type=teaching_type,
        lecturer_shortnames=get_lecturer_shortnames(lines[1]),
    )


def get_lecturer_shortnames(second_line: str) -> list[str]:
    lecturer_shorthands: list[str] = []
    words = second_line.split(" ")
    for word in words:
        if len(word) == LECTURER_SHORTHAND_SIZE:
            lecturer_shorthands.append(word)
    return lecturer_shorthands


def get_module_shorthand(first_line: str, class_name: str) -> str:
    words = first_line.split(" ")
    if len(words) < 1:
        raise RuntimeError("Cannot extract module shorthand")
    word = words[0]
    if len(words) == 1:
        for i in reversed(range(len(class_name) + 1)):
            if word.endswith(class_name[0:i]):
                word = word[: word.rfind(class_name[0:i])]
                break
    if len(word) == 0:
        raise RuntimeError("Module shorthand cannot be empty")
    return word


def get_id(
    class_name: str,
    module_shorthand: str,
    weekday: Weekday,
    start_seconds: int,
    end_seconds: int,
) -> str:
    return (
        f"{class_name}-{module_shorthand}-{weekday.index}-{start_seconds}-{end_seconds}"
    )


def get_teaching_type(third_line: str) -> TeachingType:
    if "Online" in third_line:
        return TeachingType.ONLINE
    return TeachingType.ON_SITE


def get_rooms(third_line: str) -> list[str]:
    if "DSMixe" in third_line:
        return []

    words = third_line.split(" ")
    return words
