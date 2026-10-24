"""Tests for fix_smdata_612 using small synthetic SMART Mobile exports."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fix_smdata_612 import check_sequence, fix_file, strip_nulls  # noqa: E402

PATROL = "0123456789abcdef0123456789abcdef"


def sighting(counter: int, obs_type: str, **extra: object) -> dict:
    return {
        "SMART_DataType": "patrol",
        "SMART_PatrolID": PATROL,
        "SMART_ObsCounter": counter,
        "SMART_ObservationType": obs_type,
        **extra,
    }


def feature(sight: dict | None = None, version: str = "1.0.612") -> dict:
    props: dict = {"dateTime": "2026-10-20T08:00:00.000+08:00", "deviceId": "d"}
    if sight is not None:
        props.update(ctVersion=version, latitude=-8.1, longitude=114.5, sighting=sight)
    else:
        props.update(SMART_ObservationType="waypoint", accuracy=15)
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [114.5, -8.1]}, "properties": props}


def broken_export() -> dict:
    """Mimics the 1.0.612 layout: empty fields written as null / ""."""
    nulls = {"SMART_Observer": None, "SMART_Team": None, "SMART_Comments": None, "SMART_IncidentType": None}
    return {
        "type": "FeatureCollection",
        "features": [
            feature(sighting(1, "NewPatrol", SMART_Objective="Patroli", **nulls)),
            feature(),
            feature(sighting(2, "Observation", **nulls, **{
                "c:0": "2dd92e122dbd4ddc80922a4c96e79a48",
                "a:0:a3eec3f81da24d98afcb62be519d9ce5": "catatan",
                "a:0:950b500974044af38f0346f14c5d58bb": None,
                "a:0:add2309440334d92aed6fd2c90e06d38": "",
                "SMART_Photo0:0": "/9j/AAAA",
            })),
            feature(sighting(3, "StopPatrol", SMART_Objective=None, **nulls)),
        ],
    }


class StripNullsTest(unittest.TestCase):
    def test_removes_nulls_and_empty_attributes_only(self) -> None:
        data = broken_export()
        removed = strip_nulls(data)

        self.assertEqual(removed["SMART_Observer"], 3)
        self.assertEqual(removed["SMART_Objective"], 1)
        self.assertEqual(removed["a:<n>:<attribute>"], 2)
        obs = data["features"][2]["properties"]["sighting"]
        self.assertNotIn("SMART_Observer", obs)
        self.assertEqual(obs["a:0:a3eec3f81da24d98afcb62be519d9ce5"], "catatan")
        self.assertEqual(obs["SMART_Photo0:0"], "/9j/AAAA")
        self.assertEqual(data["features"][0]["properties"]["sighting"]["SMART_Objective"], "Patroli")
        for f in data["features"]:
            for key, value in (f["properties"].get("sighting") or {}).items():
                self.assertIsNotNone(value, key)

    def test_good_export_is_unchanged(self) -> None:
        good = {"type": "FeatureCollection", "features": [
            feature(sighting(1, "NewPatrol"), "1.0.602"),
            feature(sighting(2, "StopPatrol"), "1.0.602"),
        ]}
        before = json.dumps(good, sort_keys=True)
        self.assertFalse(strip_nulls(good))
        self.assertEqual(json.dumps(good, sort_keys=True), before)


class CheckSequenceTest(unittest.TestCase):
    def test_sequential(self) -> None:
        self.assertEqual(check_sequence(broken_export()), [])

    def test_gap_is_reported(self) -> None:
        data = broken_export()
        del data["features"][2]
        self.assertEqual(len(check_sequence(data)), 1)


class FixFileTest(unittest.TestCase):
    def test_writes_fixed_copy_and_keeps_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "SMDATA_test.json"
            original = json.dumps(broken_export())
            src.write_text(original, encoding="utf-8")

            result = fix_file(src, Path(tmp) / "fixed")

            self.assertEqual(src.read_text(encoding="utf-8"), original)
            self.assertEqual(result.versions, {"1.0.612"})
            self.assertEqual((result.features, result.sightings), (4, 3))
            fixed = json.loads(result.dst.read_text(encoding="utf-8"))
            self.assertNotIn("SMART_Observer", fixed["features"][2]["properties"]["sighting"])

    def test_rejects_invalid_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{oops", encoding="utf-8")
            with self.assertRaises(ValueError):
                fix_file(bad, Path(tmp) / "out")
            bad.write_text("[1, 2]", encoding="utf-8")
            with self.assertRaises(ValueError):
                fix_file(bad, Path(tmp) / "out")


if __name__ == "__main__":
    unittest.main()
