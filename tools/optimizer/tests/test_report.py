from __future__ import annotations

from pathlib import Path

from paper_optimizer.report import build_experiment_report_view


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "report_compare_margin" / "experiment"


def _compare_report_view() -> dict:
    page = build_experiment_report_view(FIXTURE_DIR)
    assert page is not None
    return page


def test_compare_report_uses_internal_runner_up_margin_with_external_controls() -> None:
    page = _compare_report_view()

    assert "+0.0095" in page["summary_sentence"]
    assert "+0.1741" not in page["summary_sentence"]

    ranking_card = next(card for card in page["decision_cards"] if card["title"] == "Ranking Drivers")
    interpretation_card = next(card for card in page["decision_cards"] if card["title"] == "Study Interpretation")
    assert any("+0.0095" in item for item in ranking_card["items"])
    assert any("+0.0095" in item for item in interpretation_card["items"])
    assert not any("+0.1741" in item for item in interpretation_card["items"])
    caveat_card = next(card for card in page["decision_cards"] if card["title"] == "Caveats")
    assert any("gold-derived positive and negative controls" in item for item in caveat_card["items"])

    columns = [column["label"] for column in page["candidate_table"]["columns"]]
    assert "Gap To Recommended" in columns
    gap_index = columns.index("Gap To Recommended")
    runner_up = page["candidate_table"]["rows"][1]
    assert runner_up["cells"][0]["text"] == "2"
    assert runner_up["cells"][gap_index]["text"] == "-0.0095"


def test_compare_report_hero_runtime_card_is_winner_runtime() -> None:
    page = _compare_report_view()

    labels = [item["label"] for item in page["hero_meta"]]
    assert "Total Runtime" not in labels

    runtime_card = next(item for item in page["hero_meta"] if item["label"] == "Winner Runtime")
    assert runtime_card["value"] == "3.25 h"
    assert runtime_card["note"] == "winner per benchmark=1.08 h"
