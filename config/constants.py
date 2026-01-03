CLASS_PDF_INPUT_FILE = "klassen.pdf"
CLASSES_JSON_OUTPUT_FILE = "classes.json"
CLASS_PDF_TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 3,
}

TOLERANCE = 3

LECTURER_SHORTHAND_SIZE = 6
LECTURER_SHORTHAND_PDF_PDF_INPUT_FILE = "lecturer_shorthands.pdf"
LECTURER_SHORTHAND_JSON_OUTPUT_FILE = "lecturers.json"
LECTURER_SHORTHAND_PDF_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 5,
    "intersection_x_tolerance": 15,
}
LECTURER_SHORTHAND_PDF_ROW_SKIP_VALUES = ["Name Nachname Vorname", "vak"]

ALLOWED_TIMESLOTS = [
    ("8:15", "9:00"),
    ("9:15", "10:00"),
    ("10:15", "11:00"),
    ("11:15", "12:00"),
    ("12:15", "13:00"),
    ("13:15", "14:00"),
    ("14:15", "15:00"),
    ("15:15", "16:00"),
    ("16:15", "17:00"),
    ("17:15", "18:00"),
    ("18:05", "18:50"),
    ("18:50", "19:35"),
    ("19:45", "20:30"),
    ("20:30", "21:15"),
]
