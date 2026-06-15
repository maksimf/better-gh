import unittest

from app.main import _linear_identifier_from_url, _normalize_linear_identifier


class LinearIdentifierFromUrlTests(unittest.TestCase):
    def test_extracts_plain_issue_url(self) -> None:
        self.assertEqual(
            _linear_identifier_from_url(
                "https://linear.app/clearest/issue/ENG-1234"
            ),
            "ENG-1234",
        )

    def test_strips_trailing_slug_and_query(self) -> None:
        self.assertEqual(
            _linear_identifier_from_url(
                "https://linear.app/acme/issue/PROD-42/some-title-slug?foo=bar"
            ),
            "PROD-42",
        )

    def test_returns_none_for_none(self) -> None:
        self.assertIsNone(_linear_identifier_from_url(None))

    def test_returns_none_for_non_issue_url(self) -> None:
        self.assertIsNone(
            _linear_identifier_from_url("https://linear.app/clearest/team/ENG")
        )


class NormalizeLinearIdentifierTests(unittest.TestCase):
    def test_uppercases_and_trims(self) -> None:
        self.assertEqual(_normalize_linear_identifier("  eng-1234  "), "ENG-1234")

    def test_rejects_invalid_shape(self) -> None:
        self.assertIsNone(_normalize_linear_identifier("https://linear.app/foo"))
        self.assertIsNone(_normalize_linear_identifier("ENG1234"))
        self.assertIsNone(_normalize_linear_identifier("ENG-"))


if __name__ == "__main__":
    unittest.main()
