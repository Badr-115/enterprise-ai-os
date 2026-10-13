from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path


def generate(path: Path) -> None:
    rows = []
    departments = ("Sales", "Operations", "Customer Success", "Marketing")
    for index in range(25):
        current = date(2026, 1, 1) + timedelta(days=index)
        revenue = 18500 + (index % 5) * 1250 + (index // 5) * 480
        cost = round(revenue * (0.57 + (index % 3) * 0.015))
        units = 120 + (index % 7) * 14 + index * 2
        rows.append(
            {
                "Cost": cost,
                "Date": current.isoformat(),
                "Revenue": revenue,
                "Units": units,
            }
        )

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Cost", "Date", "Revenue", "Units"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "mock_data.csv")
