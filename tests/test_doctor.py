from __future__ import annotations

from paper_table_agent import cli


def test_doctor_command_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["paper-table-agent", "doctor"])
    cli.main()
