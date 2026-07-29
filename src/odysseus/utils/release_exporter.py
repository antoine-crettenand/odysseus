"""Export source-neutral artist/album/year tuples."""

import csv
import json
from pathlib import Path
from typing import Iterable, Optional, Tuple


ReleaseTuple = Tuple[str, str, Optional[int]]


def export_releases(
    releases: Iterable[ReleaseTuple],
    output_path: str,
    output_format: str = "tsv",
) -> int:
    """Write releases in a stable order and return the exported count."""
    rows = sorted(
        set(releases),
        key=lambda row: (row[0].lower(), row[1].lower(), row[2] or 0),
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "json":
        path.write_text(
            json.dumps(
                [
                    {"artist": artist, "album": album, "year": year}
                    for artist, album, year in rows
                ],
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return len(rows)

    delimiter = "\t" if output_format == "tsv" else ","
    if output_format not in {"tsv", "csv"}:
        raise ValueError("Export format must be one of: tsv, csv, json")
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter=delimiter)
        writer.writerow(["Artist", "Album", "Year"])
        writer.writerows(
            (artist, album, year if year is not None else "")
            for artist, album, year in rows
        )
    return len(rows)
