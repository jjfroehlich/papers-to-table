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


if __name__ == "__main__":
    unittest.main()
