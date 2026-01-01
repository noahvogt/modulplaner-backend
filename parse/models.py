from enum import Enum, unique
from dataclasses import dataclass
from typing import Annotated, TYPE_CHECKING

from pydantic import BaseModel, PlainSerializer, Field, ConfigDict


@dataclass
class XLevel:
    x1: float
    x2: float


@dataclass
class YLevel:
    y1: float
    y2: float


@dataclass
class HorizontalLine:
    x1: float
    x2: float
    y: float


@dataclass
class Area:
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


@dataclass(frozen=True)
class Semester:
    yyyy: int
    semester_type: SemesterType


@dataclass
class Date:
    yyyy: int
    mm: int
    dd: int


@dataclass
class Time:
    hh: int
    mm: int


@dataclass
class ExportTimestamp:
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
    AGNOSTIC = "agnostic"


@dataclass
class PageMetadata:
    semester: Semester
    export_timestamp: ExportTimestamp
    class_name: str
    degree_program: DegreeProgram


@dataclass
class UnmergedTimeEntries:
    cells: list[Area]
    horizontal_lines: list[HorizontalLine]


@dataclass(frozen=True)
class TimeSlot:
    start_time: str
    end_time: str

    def start_seconds(self) -> int:
        hours, minutes = map(int, self.start_time.split(":"))
        return hours * 3600 + minutes * 60

    def end_seconds(self) -> int:
        hours, minutes = map(int, self.end_time.split(":"))
        return hours * 3600 + minutes * 60


@dataclass
class RawExtractedModule:
    weekday: Weekday
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


@dataclass
class Teacher:
    shorthand: str
    full_name: str


# tells pydantic to to use the index field for the special Weekday Enum
CustomWeekday = Annotated[Weekday, PlainSerializer(lambda v: v.index, return_type=int)]


@dataclass
class ParsedModuleCellTextData:
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


@dataclass
class ClassPdfExtractionPageData:
    raw_extracted_modules: list[RawExtractedModule]
    page_metadata: PageMetadata
