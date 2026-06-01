import unittest

from paper_eval.compare_structured import compare_boolean, compare_categorical, compare_numeric
from paper_eval.contracts import NumericTolerance


class CompareStructuredTests(unittest.TestCase):
    def test_compare_boolean_is_deterministic(self) -> None:
        result = compare_boolean("present", "1")
        self.assertTrue(result.is_correct)

    def test_compare_categorical_uses_allowed_values_and_aliases(self) -> None:
        result = compare_categorical(
            "Canonical Label",
            "canonical-label",
            aliases={"canonical label": "Canonical Label"},
            allowed_values=["Canonical Label", "Other"],
        )
        self.assertTrue(result.is_correct)

    def test_compare_numeric_uses_global_tolerance(self) -> None:
        result = compare_numeric("10.0", "10.4", tolerance=NumericTolerance(abs_tol=0.5, rel_tol=0.0))
        self.assertTrue(result.is_correct)
        self.assertAlmostEqual(result.diagnostics["absolute_error"], 0.4)

    def test_compare_numeric_rejects_outside_tolerance(self) -> None:
        result = compare_numeric("10.0", "10.6", tolerance=NumericTolerance(abs_tol=0.5, rel_tol=0.0))
        self.assertFalse(result.is_correct)

    def test_compare_numeric_allows_interval_overlap(self) -> None:
        result = compare_numeric("1-3", "2-4", tolerance=NumericTolerance(abs_tol=0.0, rel_tol=0.0))
        self.assertTrue(result.is_correct)

    def test_compare_numeric_reports_parse_and_format_diagnostics(self) -> None:
        result = compare_numeric("65%", "65", tolerance=NumericTolerance())
        self.assertFalse(result.is_correct)
        self.assertFalse(result.diagnostics["numeric_parse_success"])
        self.assertTrue(result.diagnostics["gold_numeric_format"]["has_percent"])
        self.assertTrue(result.diagnostics["gold_numeric_format"]["has_numeric_token"])

    def test_compare_categorical_reports_alias_gap_and_list_like_values(self) -> None:
        result = compare_categorical(
            "human, mouse",
            "mouse and human",
            aliases={},
            allowed_values=["human", "mouse"],
        )
        self.assertFalse(result.is_correct)
        self.assertTrue(result.diagnostics["categorical_list_like"])
        self.assertFalse(result.diagnostics["gold_categorical"]["allowed_value_match"])

    def test_compare_boolean_reports_unknown_vocabulary_and_contradictions(self) -> None:
        unknown = compare_boolean("+", "yes")
        self.assertFalse(unknown.is_correct)
        self.assertTrue(unknown.diagnostics["gold_boolean"]["boolean_like_cue"])
        contradiction = compare_boolean("yes", "no")
        self.assertTrue(contradiction.diagnostics["boolean_contradiction"])


if __name__ == "__main__":
    unittest.main()
