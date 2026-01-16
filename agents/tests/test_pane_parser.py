import unittest

from agents.scripts import pane_parser


class PaneParserTests(unittest.TestCase):
    def test_find_last_timer_line_returns_last_match(self) -> None:
        lines = [
            "Working (1s \u2022 esc to interrupt)",
            "intermediate output",
            "Listing directory contents (2s \u2022 esc to interrupt)",
        ]

        index, line = pane_parser.find_last_timer_line(lines)

        self.assertEqual(index, 2)
        self.assertEqual(line, "Listing directory contents (2s \u2022 esc to interrupt)")

    def test_extract_timer_value_parses_duration(self) -> None:
        self.assertEqual(
            pane_parser.extract_timer_value("Working (12s \u2022 esc to interrupt)"),
            "12s",
        )
        self.assertEqual(
            pane_parser.extract_timer_value(
                "Working (3m 00s \u2022 esc to interrupt)"
            ),
            "3m 00s",
        )
        self.assertIsNone(pane_parser.extract_timer_value(None))

    def test_find_context_left_parses_percent(self) -> None:
        lines = [
            "noise",
            "100% context left - ? for shortcuts",
        ]

        percent, line = pane_parser.find_context_left(lines)

        self.assertEqual(percent, 100)
        self.assertEqual(line, "100% context left - ? for shortcuts")

    def test_find_prompt_line_detects_prompt_markers(self) -> None:
        lines = [
            "Working (2s \u2022 esc to interrupt)",
            "output line",
            "> run",
            "trailing",
        ]

        prompt_index = pane_parser.find_prompt_line(lines, 0)

        self.assertEqual(prompt_index, 2)

    def test_extract_body_lines_trims_blanks(self) -> None:
        lines = [
            "header",
            "Worked for 3s - 99% context left",
            "",
            "final answer line 1",
            "final answer line 2",
            "",
            "> prompt",
        ]

        body = pane_parser.extract_body_lines(lines, 1, 6)

        self.assertEqual(body, ["final answer line 1", "final answer line 2"])


if __name__ == "__main__":
    unittest.main()
