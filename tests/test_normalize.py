import unittest

from paper_eval.normalize import is_empty_value, normalize_boolean, normalize_categorical, normalize_numeric


class NormalizeTests(unittest.TestCase):
    def test_boolean_normalization(self) -> None:
        self.assertTrue(normalize_boolean("Yes"))
        self.assertFalse(normalize_boolean("negative"))
        self.assertIsNone(normalize_boolean("maybe"))

    def test_categorical_normalization_uses_aliases(self) -> None:
        value = normalize_categorical(
            " Alpha-Beta ",
            aliases={"alpha beta": "canonical label"},
            allowed_values=["canonical label", "other"],
        )
        self.assertEqual(value, "canonical label")

    def test_numeric_normalization_supports_range_and_approximate(self) -> None:
        interval = normalize_numeric("1.0 - 2.5")
        approx = normalize_numeric("approx 3.4")
        self.assertEqual(interval.kind, "interval")
        self.assertEqual(interval.lower, 1.0)
        self.assertEqual(interval.upper, 2.5)
        self.assertTrue(approx.approx)
        self.assertEqual(approx.center, 3.4)

    def test_empty_detection_distinguishes_blank_from_na(self) -> None:
        self.assertTrue(is_empty_value("   "))
        self.assertTrue(is_empty_value(None))
        self.assertFalse(is_empty_value("NA"))


if __name__ == "__main__":
    unittest.main()
