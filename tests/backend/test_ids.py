from backend.app.ids import make_cell_id, make_proposal_id


def test_cell_id_is_deterministic() -> None:
    first = make_cell_id("Paper A", "Accuracy")
    second = make_cell_id("Paper A", "Accuracy")
    assert first == second


def test_proposal_id_contains_pdf_context_uniqueness() -> None:
    same_cell_different_pdf_1 = make_proposal_id("run_1", "pdf_1", "cell_1")
    same_cell_different_pdf_2 = make_proposal_id("run_1", "pdf_2", "cell_1")
    assert same_cell_different_pdf_1 != same_cell_different_pdf_2
