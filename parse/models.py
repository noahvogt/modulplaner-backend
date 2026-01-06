from enum import Enum, unique
from typing import Annotated, Any

from pydantic import BaseModel, PlainSerializer, Field, ConfigDict, BeforeValidator


class XLevel(BaseModel):
    x1: float
    x2: float


class YLevel(BaseModel):
    y1: float
    y2: float


class HorizontalLine(BaseModel):
    x1: float
    x2: float
    y: float


class Area(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


@unique
class Weekday(Enum):
    MONTAG = ("Montag", 0)
    DIENSTAG = ("Dienstag", 1)
    MITTWOCH = ("Mittwoch", 2)
    DONNERSTAG = ("Donnerstag", 3)
    FREITAG = ("Freitag", 4)
    SAMSTAG = ("Samstag", 5)
    SONNTAG = ("Sonntag", 6)

    def __init__(self, display_name, index):
        self.display_name = display_name
        self.index = index


@unique
class SemesterType(Enum):
    HS = "Herbstsemester"
    FS = "Frühlingssemester"


class Semester(BaseModel):
    model_config = ConfigDict(frozen=True)
    yyyy: int
    semester_type: SemesterType


class Date(BaseModel):
    yyyy: int
    mm: int
    dd: int


class Time(BaseModel):
    hh: int
    mm: int


class ExportTimestamp(BaseModel):
    date: Date
    time: Time


@unique
class DegreeProgram(Enum):
    DATASCIENCE = "Data Science"
    ELEK_U_INFO = "Elektro- und Informationstechnik"
    ENER_U_UMWELT = "Energie- und Umwelttechnik"
    ICOMPETENCE = "iCompetence"
    INFORMATIK = "Informatik"
    KONTEXT_BWL = "Kontext BWL"
    KONTEXT_ENGLISCH = "Kontext Englisch"
    KONTEXT_GSW = "Kontext GSW"
    KONTEXT_KOMM = "Kontext Kommunikation"
    MIXED_BWL_GSW_KOMM = "Mixed BWL, GSW, Kommunikation"
    MASCHINENBAU = "Maschinenbau"
    SYSTEMTECHNIK = "Systemtechnik"
    WIRTSCHAFT_ING = "Wirtschaftsingenieurwesen"
    AGNOSTIC = "SG-???"


class PageMetadata(BaseModel):
    semester: Semester
    export_timestamp: ExportTimestamp
    class_name: str
    degree_program: DegreeProgram


class UnmergedTimeEntries(BaseModel):
    cells: list[Area]
    horizontal_lines: list[HorizontalLine]


class TimeSlot(BaseModel):
    model_config = ConfigDict(frozen=True)
    start_time: str
    end_time: str

    def start_seconds(self) -> int:
        hours, minutes = map(int, self.start_time.split(":"))
        return hours * 3600 + minutes * 60

    def end_seconds(self) -> int:
        hours, minutes = map(int, self.end_time.split(":"))
        return hours * 3600 + minutes * 60


def to_tuple_if_list(v: Any) -> Any:
    if isinstance(v, list):
        return tuple(v)
    return v


# needed for pydantic to correctly parse the custom Weekday Enum
TolerantWeekday = Annotated[Weekday, BeforeValidator(to_tuple_if_list)]


class RawExtractedModule(BaseModel):
    weekday: TolerantWeekday
    start_seconds: int
    end_seconds: int
    text: str
    source_page_number: int


@unique
class TeachingType(Enum):
    ON_SITE = "on_site"
    ONLINE = "online"
    HYBRID = "hybrid"
    BLOCK = "blockmodule"


class RawLecturer(BaseModel):
    """
    Basic representation of an extracted lecturer from a pdf that needs to be parsed.
    """

    shorthand: str
    firstname: str
    surname: str


class Lecturer(BaseModel):
    """
    JSON-serializable representation of a parsed lecturer ready to be exported.
    """

    short: str
    surname: str
    firstname: str


# tells pydantic to to use the index field for the special Weekday Enum
CustomWeekday = Annotated[Weekday, PlainSerializer(lambda v: v.index, return_type=int)]


class ParsedModuleCellTextData(BaseModel):
    module_shorthand: str
    degree_program: DegreeProgram
    class_name: str
    rooms: list[str]
    part_of_other_classes: list[str]
    teaching_type: TeachingType
    lecturer_shortnames: list[str]


class ClassJsonModule(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    weekday: CustomWeekday
    module_shorthand: str = Field(..., alias="name")
    start_seconds: int = Field(..., alias="from")
    end_seconds: int = Field(..., alias="to")
    degree_program: DegreeProgram = Field(..., alias="degree_prg")
    class_name: str = Field(..., alias="class")
    rooms: list[str]
    pages: list[int]
    part_of_other_classes: list[str]
    id: str
    teaching_type: TeachingType
    lecturer_shorthands: list[str] = Field(..., alias="teachers")


class ClassPdfExtractionPageData(BaseModel):
    raw_extracted_modules: list[RawExtractedModule]
    page_metadata: PageMetadata


class StartsWithMatch(BaseModel):
    shorthand_found: str
    num_of_matches: int
