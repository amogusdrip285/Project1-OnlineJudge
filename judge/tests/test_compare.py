import unittest

from judge.compare import normalize_output, outputs_match


class TestCompare(unittest.TestCase):
    def test_exact_match(self) -> None:
        self.assertTrue(outputs_match("8\n-2\n15\n0\n", "8\n-2\n15\n0\n"))

    def test_crlf_and_lf_match(self) -> None:
        self.assertTrue(outputs_match("8\r\n-2\r\n", "8\n-2\n"))

    def test_trailing_spaces_and_tabs_ignored(self) -> None:
        self.assertTrue(outputs_match("8   \n-2\t\t\n", "8\n-2"))

    def test_trailing_empty_lines_ignored(self) -> None:
        self.assertTrue(outputs_match("8\n-2\n\n\n", "8\n-2\n"))

    def test_leading_whitespace_not_ignored(self) -> None:
        self.assertFalse(outputs_match(" 8\n", "8\n"))

    def test_internal_blank_lines_preserved(self) -> None:
        self.assertFalse(outputs_match("8\n\n-2\n", "8\n-2\n"))

    def test_empty_outputs_match(self) -> None:
        self.assertEqual(normalize_output("\r\n\n  \t \n"), "")
        self.assertTrue(outputs_match("", "\n\n"))

    def test_real_difference_fails(self) -> None:
        self.assertFalse(outputs_match("8\n-1\n", "8\n-2\n"))


if __name__ == "__main__":
    unittest.main()
