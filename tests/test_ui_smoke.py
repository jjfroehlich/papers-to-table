from __future__ import annotations

import pytest


def test_ui_import_smoke() -> None:
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    app = AppTest.from_file("paper_table_agent/ui/app.py")
    app.run()
    assert not app.exception
