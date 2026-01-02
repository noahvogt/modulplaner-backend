# modulplaner-backend

Provides backend tooling for [modulplaner](https://codeberg.org/Modulplaner/modulplaner).

Because the original repo only contains frontend code and data updates were slow and intransparent, I created this repo as a solution.

## Basic Usage

After installing the [python3](https://www.python.org/) dependencies in `requirements.txt`, execute `parse_class_pdf.py` to parse a class timetable PDF.

```bash
./parse_class_pdf.py [-h] [-l LECTURERS] [-i INPUT] [-o OUTPUT] [lecturers_pos]
```

### Arguments

- `-i`, `--input`: Path to the input PDF file. Defaults to `klassen.pdf`.
- `-o`, `--output`: Path to the output JSON file. Defaults to `classes.json`.
- `-l`, `--lecturers` or `lecturers_pos`: Path to the `lecturers.json` file. If provided, it is used to validate lecturer shorthands during parsing.

The default values for input and output files are defined in `config/constants.py`.

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
- degree_program's `Kontext BWL`, `Kontext Kommunikation`, `Kontext GSW` have mixed classes, which arises the need the have a table to differentiate the modules

## Problems in the Frontend Data Formats
- there seem to be `teaching_type`'s defined that may not ever be found in class pdf's
- changes and deprecation in lecturer shorthands are not possible without breaking the view of older semesters
- the usefulness of `part_of_other_classes` needs to be further investigated

## Licensing
modulplaner-backend is a free (as in “free speech” and also as in “free beer”) Software. It is distributed under the GNU Affero General Public License v3 (or any later version) - see the accompanying LICENSE file for more details.
