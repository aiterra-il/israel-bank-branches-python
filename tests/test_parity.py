from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import israel_bank_branches
from israel_bank_branches import (
    find_branch,
    get_branch,
    is_closed,
    load_banks,
    load_branches,
    map_url,
    nearest_branches,
    search_branches,
    short_bank_name,
    to_bank,
    to_branch,
)

FIXTURES = json.loads(Path(__file__).with_name("fixtures.json").read_text(encoding="utf-8"))
LIVE = os.environ.get("LIVE") == "1"


def keys(branches):
    return [[branch["bank_code"], branch["code"], branch["closed_on"]] for branch in branches]


class ParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.branches = [to_branch(case["record"]) for case in FIXTURES["branch_records"]][:-3]

    def test_records_become_branches(self):
        self.assertGreater(len(FIXTURES["branch_records"]), 1000)
        for case in FIXTURES["branch_records"]:
            self.assertEqual(to_branch(case["record"]), case["branch"], case["record"])

    def test_records_become_banks(self):
        for case in FIXTURES["bank_records"]:
            self.assertEqual(to_bank(case["record"]), case["bank"], case["record"])

    def test_short_bank_name(self):
        for name, expected in FIXTURES["short_bank_name"]:
            self.assertEqual(short_bank_name(name), expected, name)

    def test_closed_branches(self):
        self.assertEqual([is_closed(branch) for branch in self.branches], FIXTURES["is_closed"])

    def test_map_url(self):
        self.assertEqual([map_url(branch) for branch in self.branches], FIXTURES["map_url"])

    def test_find_branch(self):
        for case in FIXTURES["find"]:
            self.assertEqual(find_branch(self.branches, *case["args"]), case["result"], case["args"])

    def test_search_branches(self):
        for case in FIXTURES["search"]:
            found = search_branches(self.branches, case["query"], **case["kwargs"])
            self.assertEqual(keys(found), case["result"], (case["query"], case["kwargs"]))

    def test_nearest_branches(self):
        for case in FIXTURES["nearest"]:
            found = nearest_branches(self.branches, *case["args"], **case["kwargs"])
            self.assertEqual(
                [[branch["bank_code"], branch["code"], branch["distance_km"]] for branch in found],
                case["result"],
                (case["args"], case["kwargs"]),
            )


class PackageTest(unittest.TestCase):
    def test_package_is_typed_and_versioned(self):
        self.assertTrue(Path(israel_bank_branches.__file__).with_name("py.typed").exists())
        self.assertRegex(israel_bank_branches.__version__, r"^\d+\.\d+\.\d+$")

    def test_package_ships_no_data(self):
        package = Path(israel_bank_branches.__file__).parent
        self.assertEqual(sorted(path.name for path in package.iterdir() if path.suffix in (".json", ".csv")), [])


@unittest.skipUnless(LIVE, "set LIVE=1 to call data.gov.il")
class LiveTest(unittest.TestCase):
    def test_branches_load(self):
        branches = load_branches()
        self.assertGreater(len(branches), 1000)
        self.assertEqual(get_branch(12, 532)["bank_name"], "בנק הפועלים")

    def test_banks_include_swift_codes(self):
        banks = load_banks()
        self.assertEqual(next(bank for bank in banks if bank["code"] == 12)["swift"], "POALILITXXX")


if __name__ == "__main__":
    unittest.main()
