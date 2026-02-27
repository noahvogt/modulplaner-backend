# modulplaner-backend

Provides backend tooling for [modulplaner-frontend](https://codeberg.org/Modulplaner/modulplaner) (archived at [#1](https://github.com/noahvogt/modulplaner-frontend) [#2](https://git.noahvogt.com/noah/modulplaner-frontend)).

Because the original repo only contains frontend code and data updates were slow and intransparent, I created this repo (archived at [#1](https://github.com/noahvogt/modulplaner-backend) [#2](https://git.noahvogt.com/noah/modulplaner-backend)) as a solution.

## Project Status & Roadmap

Currently the core data generation is pretty solid. This projects was built to support API version 1.0.0 of [modulplaner-openapi-spec](https://codeberg.org/Modulplaner/openapi) (archived at [#1](https://github.com/noahvogt/modulplaner-openapi-spec) [#2](https://git.noahvogt.com/noah/modulplaner-openapi-spec)). Currently I am part of the team at [FHNW](https://fhnw.ch) that works on an implementation of the API Version 2.x.x. Instead of parsing pdf files, the goal is the get the data directly from [evento](https://www.swisslearninghub.com/en/angebot/evento-campus-management/), the campus managment software used at FHNW. The associated repositories for this rewrite are currently only visible to circa 10 members of a GitLab group on the [FHNW GitLab instace](https://gitlab.fhnw.ch).

For this specific repo, the backlog is the following:

- adding documentation on how the extraction works, and problems with this approach
- addressing the problems in the source data and the frontend data formats (see the following sections)
- verifying module / lecturer shorthands and rooms in class pdf cells
- fixing module mapping + verification
- fixing module dependencies

## Installation

You need to install

- [python3](https://www.python.org)
- the python dependencies in `requirements.txt`

For some simple commands mentioned in this documentation, It is also recommended to install and setup

- [jq](https://github.com/jqlang/jq)
- a working POSIX shell environment

## Terminology

This project uses specific domain terms that map to the data sources and the generated JSON structure:

- **Class Timetable PDF**: The primary source file (e.g., `klassen.pdf`) containing the weekly schedule.
- **Lecturer Shorthands PDF**: A source file mapping Lecturer abbreviations (shorthands) to their full names.
- **Lecturers Timetable PDF**: A secondary source file, similar to the Class Timetable PDF, but grouped by Lecturer (typically one page per Lecturer) instead of by class.
- **Module**: A formally defined course unit within the curriculum that has specified learning objectives and contents. Every Module has an official shorthand, an official ID, a webpage, and provides a specific amount of ECTS credits. A Module may be offered multiple times and in different formats. Students cannot enroll in a Module directly.
- **Module Run**: A specific delivery of a Module in a given period (e.g., semester or academic year) where students can enroll. Different runs of the same Module may vary in schedule, Lecturers, or location, while sharing the same course unit. Students can enroll in Module Runs.
- **Module Shorthand**: The official abbreviation for a Module.
- **Class**: A grouping used to uniquely identify specific Module Runs. Students do not have to enroll in every Module Run of a Class; they are usually part of multiple Classes as they enroll in distinct Module Runs that are part of various Classes.
- **Lecturer**: A teacher who instructs a specific Module Run.
- **Lecturer Shorthand**: An abbreviation for a Lecturer. Since there are multiple abbreviations found in the source data for the same Lecturer, they cannot be used to uniquely identify Lecturers.

## Basic Usage

This section is split into the different script provided by this repository.

### generate_classes_json.py

Execute the following to parse a class timetable PDF into the `classes.json` file needed by the frontend.

```sh
./generate_classes_json.py -i klassen.pdf -o classes.json
```

For more information, show the cli arguments via `./generate_classes_json.py -h`.

#### Faster Development Cycle

Since the PDF extraction takes a significant amount of time, you can split the process into two stages:

1.  **Stage 1 (Extraction):** Run once and save the result: `./generate_classes_json.py --save-intermediate data.pkl`
2.  **Stage 2 (Parsing):** Load the saved data and iterate on the parsing logic: `./generate_classes_json.py --load-intermediate data.pkl --output classes.json`

### extract_lecturer_shorthands_pdf.py

Use this script to parse a lecturer shortname PDF into the `lecturers.json` file needed by the frontend. Note that if you don't merge the script output with your previous `lecuturer.json` file, the view of previous semesters may break. You can easily do that using `jq`:

```sh
jq -s 'add | unique' previous_lecturers.json script_output.json > merged.json
```

For more information, show the cli arguments via `./extract_lecturer_shorthands_pdf.py -h`.

### rip_modulplaner_frontend_data.py

Rips all data files from a live modulplaner-frontend server.

For more information, show the cli arguments via `./rip_modulplaner_frontend_data.py -h`.


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
