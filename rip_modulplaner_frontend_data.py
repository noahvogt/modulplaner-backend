#!/usr/bin/env python3

import os
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from argparse import ArgumentParser

import requests

from config import (
    FRONTEND_RIPPER_BASE_FILES,
    FRONTEND_RIPPER_BASE_URL_DEFAULT,
    FRONTEND_RIPPER_OUTPUT_DIR_DEFAULT,
    FRONTEND_RIPPER_SEMESTER_VERSIONS_FILE,
    REQUESTS_TIMEOUT,
)


def download_file(url: str, local_path: Path) -> bool:
    """
    Downloads a file URL and returns wether it went successfully.
    """
    try:
        response = requests.get(url, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(response.content)
        logging.info("Downloaded: %s", local_path)
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logging.warning("File not found (404): %s", url)
        else:
            logging.error("Failed to download %s: %s", url, e)
        return False
    except Exception as e:
        logging.error("Error downloading %s: %s", url, e)
        return False


def get_semester_versions(
    base_url: str, output_dir: Path
) -> Optional[List[Dict[str, Any]]]:
    """
    Downloads and parses the semester-versions.json file.
    """
    logging.info("Fetching semester list...")
    if not download_file(
        f"{base_url}/{FRONTEND_RIPPER_SEMESTER_VERSIONS_FILE}",
        output_dir / FRONTEND_RIPPER_SEMESTER_VERSIONS_FILE,
    ):
        logging.error("Could not download semester-versions.json. Exiting.")
        return None

    try:
        with open(
            output_dir / FRONTEND_RIPPER_SEMESTER_VERSIONS_FILE, "r", encoding="utf-8"
        ) as f:
            return json.load(f)
    except json.JSONDecodeError:
        logging.error("Error parsing semester-versions.json")
        return None


def process_semester(semester: str, base_url: str, output_dir: Path) -> None:
    """
    Downloads files associated with a specific semester.
    """
    logging.info("Processing Semester: %s", semester)

    semester_level_files = ["blockclasses.json", "config.json"]
    for s_file in semester_level_files:
        download_file(f"{base_url}/{semester}/{s_file}", output_dir / semester / s_file)

    config_path = output_dir / semester / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                blockclass_file = config_data.get("blockclass_file")
                if blockclass_file:
                    download_file(
                        f"{base_url}/{semester}/{blockclass_file}",
                        output_dir / semester / blockclass_file,
                    )
        except (json.JSONDecodeError, OSError) as e:
            logging.error("Error reading config.json for %s: %s", semester, e)


def process_version(
    semester: str, version: str, base_url: str, output_dir: Path
) -> None:
    """
    Downloads files associated with a specific version of a semester.
    """
    version_level_files = ["classes.json", "config.json", "klassen.pdf"]

    for v_file in version_level_files:
        download_file(
            f"{base_url}/{semester}/{version}/{v_file}",
            output_dir / semester / version / v_file,
        )


def main():
    parser = ArgumentParser(
        description="Rips all data files from a live modulplaner-frontend server."
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for the data",
        default=FRONTEND_RIPPER_BASE_URL_DEFAULT,
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for downloaded files",
        default=FRONTEND_RIPPER_OUTPUT_DIR_DEFAULT,
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    base_url = args.base_url
    output_dir = Path(args.output_dir)

    for filename in FRONTEND_RIPPER_BASE_FILES:
        download_file(f"{base_url}/{filename}", output_dir / filename)

    semester_data = get_semester_versions(base_url, output_dir)
    if semester_data is None:
        return

    for item in semester_data:
        semester = item.get("semester")
        versions = item.get("versions", [])

        if not semester:
            continue

        process_semester(semester, base_url, output_dir)

        for version in versions:
            process_version(semester, version, base_url, output_dir)


if __name__ == "__main__":
    main()
