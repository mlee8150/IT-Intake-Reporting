"""Loads the department -> function rollup used by panel 5 (Where demand comes from)."""
from __future__ import annotations

import csv
from pathlib import Path


class DepartmentMapping:
    def __init__(self, department_to_function: dict[str, str]):
        self._department_to_function = department_to_function

    @classmethod
    def from_csv(cls, path: Path) -> "DepartmentMapping":
        if not path.exists():
            raise FileNotFoundError(
                f"Department mapping not found at {path}. Copy "
                f"config/department_mapping.example.csv to {path.name} and fill in "
                "your real department -> function rollup."
            )
        mapping: dict[str, str] = {}
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                mapping[row["department"].strip()] = row["function"].strip()
        return cls(mapping)

    def function_for(self, department: str) -> str:
        try:
            return self._department_to_function[department.strip()]
        except KeyError:
            raise KeyError(
                f"No function mapping for department {department!r}. "
                "Add it to the department mapping CSV."
            ) from None
