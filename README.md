# modulplaner-backend

Provides backend tooling for [modulplaner](https://codeberg.org/Modulplaner/modulplaner).

Because the original repo only contains frontend code and data updates were slow and intransparent, I created this repo as a solution.

## Installation

You need to install

- [python3](https://www.python.org)
- the python dependencies in `requirements.txt`

For some simple commands mentioned in this documentat, It is also recommended to install and setup

- [jq](https://github.com/jqlang/jq)
- a working POSIX shell environment

## Basic Usage

This section is split into the different script provided by this repository.

### parse_class_pdf.py

Execute the following to parse a class timetable PDF into the `classes.json` file needed by the frontend.

```sh
./parse_class_pdf.py [-h] [-l LECTURERS] [-i INPUT] [-o OUTPUT] [--save-intermediate SAVE_INTERMEDIATE] [--load-intermediate LOAD_INTERMEDIATE]
```

#### Arguments

- `-i`, `--input`: Path to the input PDF file. Defaults to `klassen.pdf`.
- `-o`, `--output`: Path to the output JSON file. Defaults to `classes.json`.
- `-l`, `--lecturers`: Path to the `lecturers.json` file. If provided, it is used to validate lecturer shorthands during parsing.
- `--save-intermediate`: Path to save the intermediate extraction data (pickle format) and exit. Useful for skipping the slow extraction stage in subsequent runs.
- `--load-intermediate`: Path to load the intermediate extraction data from (pickle format) and skip extraction.

The default values for input and output files are defined in `config/constants.py`.

#### Faster Development Cycle

Since the PDF extraction takes a significant amount of time, you can split the process into two stages:

1.  **Stage 1 (Extraction):** Run once and save the result: `./parse_class_pdf.py --save-intermediate data.pkl`
2.  **Stage 2 (Parsing):** Load the saved data and iterate on the parsing logic: `./parse_class_pdf.py --load-intermediate data.pkl --output classes.json`

### extract_lecturer_shorthands_pdf.py

Use this script to parse a lecturer shortname PDF into the `lecturers.json` file needed by the frontend. Note that if you don't merge the script output with your previous `lecuturer.json` file, the view of previous semesters may break. You can easily do that using `jq`:

```sh
jq -s 'add | unique' previous_lecturers.json script_output.json > merged.json
```

For more information, show the cli arguments via `./extract_lecturer_shorthands_pdf.py -h`.

### rip_modulplaner_frontend_data.py

Rips all data files from a live modulplaner-frontend server.

For more information, show the cli arguments via `./rip_modulplaner_frontend_data.py -h`.

## Project Roadmap

Currently I am working on refining the core data generation. In the future, I can see myself also working on:

- adding documentation on how the extraction works, and problems with this approach
- adding documentation on the json's the frontend excepts, formulate json shemas
- addressing the problems in the source data and the frontend data formats (see the following sections)
- verifying module / lecturer shorthands and rooms in class pdf cells
- fixing module mapping + verification
- fixing module dependencies

## Problems in the Source Data
- class pdf's cells sometimes cut off data like lecturer shorthands, which could be repaired by cross-referencing with the lecturer pdf
- Unclear `DSMixe` entry in the room line (third line) of class pdf cells, or the line is missing altogether
- Non-Ascii Characters are present (e.g. for lecturer shorthands)
- The redundant class name in the class pdf cells sometimes gets mixed up with the module shorthand, which is especially annoying when part of the class name gets cut off too (is handled)
- missing degree programs in the text above the table need to be guessed via ugly heuristics
- there is a class called `alle` which is degree program agnostic
- degree_program's `Kontext BWL`, `Kontext Kommunikation`, `Kontext GSW` have mixed classes, which arises the need the have a table to differentiate the modules based on their shorthands
- some lecturers shorthands present in class timetable pdf's are missing altogether in both the lecturer shorthands pdf and the lecturers timetable pdf
- there are different lecturer shorthands for the same full name lecturer in the lecturer shorthands pdf and the lecturer timetable pdf
- there are timeslots for modules - which are part of the same class - that are found in the class timetable pdf but not the lecturer pdf

## Problems in the Frontend Data Formats
- there seem to be `teaching_type`'s defined that may not ever be found in class pdf's
- changes and deprecation in lecturer shorthands are not possible without breaking the view of older semesters
- the usefulness of `part_of_other_classes` needs to be further investigated

## Licensing
modulplaner-backend is a free (as in “free speech” and also as in “free beer”) Software. It is distributed under the GNU Affero General Public License v3 (or any later version) - see the accompanying LICENSE file for more details.
