"""Tests of the level enumeration and of the ``--level`` selector grammar."""

import pytest

from uci_test_suite.levels import Level, format_levels, parse_levels


class TestParseLevels:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("0", {0}),
            ("6", {6}),
            (" 3 ", {3}),
            ("0-2", {0, 1, 2}),
            ("2-2", {2}),
            ("0-6", {0, 1, 2, 3, 4, 5, 6}),
            ("0-2,5", {0, 1, 2, 5}),
            ("1,2,4", {1, 2, 4}),
            ("5,0-2", {0, 1, 2, 5}),
            ("1-3,2-4", {1, 2, 3, 4}),
        ],
    )
    def test_accepted(self, text: str, expected: set[int]) -> None:
        assert parse_levels(text) == {Level(value) for value in expected}

    @pytest.mark.parametrize(
        "text",
        ["", "-2", "3-", "-", "0:2", "0..2", "1;2", "two", "0-2-4", "7", "0-7", "-1", "0, ,2", "l2", "+2"],
    )
    def test_rejected(self, text: str) -> None:
        with pytest.raises(ValueError):
            parse_levels(text)

    def test_a_countdown_range_is_rejected_with_the_right_advice(self) -> None:
        with pytest.raises(ValueError, match="2-4"):
            parse_levels("4-2")

    def test_a_missing_level_says_the_range(self) -> None:
        with pytest.raises(ValueError, match="levels are 0 to 6"):
            parse_levels("9")


class TestLevel:
    def test_tags_and_titles(self) -> None:
        assert Level.PROCESS.tag == "L0"
        assert Level.ACCEPTANCE.tag == "L6"
        assert Level.SESSION.title == "Session"
        assert str(Level.PLAY) == "L2 Play"

    def test_every_level_has_a_summary(self) -> None:
        assert all(level.summary for level in Level)

    @pytest.mark.parametrize(
        ("levels", "expected"),
        [
            (set(), "none"),
            ({Level.PLAY}, "L2"),
            ({Level.PROCESS, Level.HANDSHAKE, Level.PLAY}, "L0-L2"),
            ({Level.PROCESS, Level.HANDSHAKE, Level.PLAY, Level.ROBUSTNESS}, "L0-L2, L5"),
            ({Level.HANDSHAKE, Level.SESSION, Level.OPTIONAL}, "L1, L3-L4"),
        ],
    )
    def test_formatting(self, levels: set[Level], expected: str) -> None:
        assert format_levels(levels) == expected
