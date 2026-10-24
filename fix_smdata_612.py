#!/usr/bin/env python3
"""Repair SMART Mobile 1.0.612 patrol exports so SMART Desktop can import them.

SMART Mobile build 1.0.612 writes empty patrol/observation fields as JSON
``null`` (``SMART_Observer``, ``SMART_Team``, ``SMART_Comments``,
``SMART_IncidentType``, ``SMART_Objective`` and empty ``a:<n>:<uuid>``
attributes). Build 1.0.602 simply omitted those keys.

SMART Desktop's importer (CtJsonObservationParser.createWaypoint) does::

    String ob = (String) observations.get("SMART_Observer");
    if (ob.startsWith("e:")) ...

so every Observation carrying ``"SMART_Observer": null`` throws a
NullPointerException. The feature is skipped, ``lastObservationCnt`` never
advances, and because the importer requires SMART_ObsCounter to be strictly
sequential, every later observation of the patrol (including StopPatrol) is
skipped as well.

This script removes every null-valued key (and every empty-string
attribute) from each feature's ``sighting``
object, restoring the 1.0.602 layout. Nothing else is changed.

Usage:
    python fix_smdata_612.py SMDATA_*.json [-o fixed/]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


def strip_nulls(data: dict) -> Counter[str]:
    """Remove null-valued keys and empty attributes from every sighting in-place.

    Returns a counter of removed keys (UUID-bearing keys are collapsed to
    their prefix so the summary stays readable).
    """
    removed: Counter[str] = Counter()
    for feature in data.get("features", []):
        sighting = (feature.get("properties") or {}).get("sighting")
        if not isinstance(sighting, dict):
            continue
        # Empty-string attributes (e.g. an unfilled DATE) fail Desktop's
        # parsers too; for TEXT they carry no information, so drop them all.
        empty = [k for k, v in sighting.items() if v is None or (v == "" and k.startswith("a:"))]
        for key in empty:
            del sighting[key]
            removed["a:<n>:<attribute>" if key.startswith("a:") else key] += 1
    return removed


def check_sequence(data: dict) -> list[str]:
    """Verify SMART_ObsCounter is 1..N per patrol (the importer requires it)."""
    counters: dict[str, list[int]] = {}
    for feature in data.get("features", []):
        sighting = (feature.get("properties") or {}).get("sighting")
        if isinstance(sighting, dict) and "SMART_ObsCounter" in sighting:
            counters.setdefault(sighting.get("SMART_PatrolID"), []).append(sighting["SMART_ObsCounter"])
    return [
        f"patrol {pid}: SMART_ObsCounter not sequential"
        for pid, seq in counters.items()
        if sorted(seq) != list(range(1, len(seq) + 1))
    ]


@dataclass
class FixResult:
    """Outcome of repairing one SMDATA file."""

    src: Path
    dst: Path
    removed: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)
    versions: set[str] = field(default_factory=set)
    features: int = 0
    sightings: int = 0


def fix_file(src: Path, output_dir: Path) -> FixResult:
    """Read ``src``, strip null/empty values and write it to ``output_dir``.

    Raises OSError / json.JSONDecodeError / ValueError if the file cannot be
    read or is not a SMART Mobile GeoJSON export.
    """
    data = json.loads(src.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise ValueError("bukan file export SMART Mobile (tidak ada 'features')")

    result = FixResult(src=src, dst=output_dir / src.name, features=len(data["features"]))
    for feature in data["features"]:
        props = feature.get("properties") or {}
        if isinstance(props.get("sighting"), dict):
            result.sightings += 1
            if props.get("ctVersion"):
                result.versions.add(props["ctVersion"])

    result.removed = strip_nulls(data)
    result.problems = check_sequence(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.dst.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+", type=Path, help="SMDATA_*.json files exported by SMART Mobile")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("fixed"), help="output folder (default: fixed/)")
    args = parser.parse_args()

    status = 0
    for src in args.inputs:
        try:
            result = fix_file(src, args.output_dir)
        except (OSError, ValueError) as exc:
            print(f"[FAIL] {src}: {exc}", file=sys.stderr)
            status = 1
            continue

        print(f"[OK]   {src.name} -> {result.dst}")
        for key, count in sorted(result.removed.items()):
            print(f"         removed null/empty {key}: {count}")
        for problem in result.problems:
            print(f"         WARNING {problem}")
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
