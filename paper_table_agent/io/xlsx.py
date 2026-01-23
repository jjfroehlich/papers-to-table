from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class TableData:
    dataframe: pd.DataFrame
    sheet_name: str

    @property
    def columns(self) -> list[str]:
        return list(self.dataframe.columns)

    def preview(self, n: int = 5) -> pd.DataFrame:
        return self.dataframe.head(n)


def load_table(path: Path, sheet_name: str | None = None) -> TableData:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        dataframe = pd.read_csv(path)
        resolved_sheet = sheet_name or path.stem
        return TableData(dataframe=dataframe, sheet_name=resolved_sheet)
    sheet = sheet_name or 0
    dataframe = pd.read_excel(path, sheet_name=sheet)
    return TableData(dataframe=dataframe, sheet_name=sheet_name or str(sheet))


def write_table_copy(table: TableData, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".csv":
        table.dataframe.to_csv(output_path, index=False)
    else:
        table.dataframe.to_excel(output_path, index=False)
