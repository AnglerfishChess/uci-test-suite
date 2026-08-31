"""Unit tests for the engine-to-GUI line parsers."""

import pytest

from uci_test_suite.protocol import (
    LineKind,
    OptionType,
    ProtocolError,
    classify,
    is_lan_move,
    keyword_of,
    parse_bestmove,
    parse_id,
    parse_info,
    parse_option,
)


class TestClassify:
    @pytest.mark.parametrize(
        ("line", "kind"),
        [
            ("uciok", LineKind.UCIOK),
            ("readyok", LineKind.READYOK),
            ("id name Stockfish 17", LineKind.ID),
            ("option name Hash type spin default 16 min 1 max 1024", LineKind.OPTION),
            ("info depth 1 score cp 20", LineKind.INFO),
            ("bestmove e2e4", LineKind.BESTMOVE),
            ("copyprotection checking", LineKind.COPYPROTECTION),
            ("registration ok", LineKind.REGISTRATION),
            ("", LineKind.EMPTY),
            ("   ", LineKind.EMPTY),
            ("Stockfish 17 by the Stockfish developers", LineKind.UNKNOWN),
        ],
    )
    def test_kinds(self, line: str, kind: LineKind) -> None:
        assert classify(line) is kind

    def test_leading_junk_is_skipped(self) -> None:
        assert classify("garbage bestmove e2e4") is LineKind.BESTMOVE
        assert keyword_of("garbage bestmove e2e4") == "bestmove"

    def test_no_keyword(self) -> None:
        assert keyword_of("just some words") is None


class TestParseId:
    def test_name(self) -> None:
        parsed = parse_id("id name Stockfish 17")
        assert parsed is not None
        assert (parsed.key, parsed.value) == ("name", "Stockfish 17")

    def test_author_keeps_spaces(self) -> None:
        parsed = parse_id("id author the Stockfish developers (see AUTHORS file)")
        assert parsed is not None
        assert parsed.value == "the Stockfish developers (see AUTHORS file)"

    def test_other_line(self) -> None:
        assert parse_id("uciok") is None

    def test_value_required(self) -> None:
        with pytest.raises(ProtocolError):
            parse_id("id name")


class TestParseOption:
    def test_spin(self) -> None:
        option = parse_option("option name Hash type spin default 16 min 1 max 1024")
        assert option is not None
        assert option.name == "Hash"
        assert option.type is OptionType.SPIN
        assert (option.default, option.min, option.max) == ("16", 1, 1024)
        assert option.issues() == ()

    def test_check(self) -> None:
        option = parse_option("option name Ponder type check default false")
        assert option is not None
        assert option.type is OptionType.CHECK
        assert option.default == "false"
        assert option.issues() == ()

    def test_combo(self) -> None:
        option = parse_option("option name Style type combo default Normal var Solid var Normal var Risky")
        assert option is not None
        assert option.type is OptionType.COMBO
        assert option.default == "Normal"
        assert option.var == ("Solid", "Normal", "Risky")
        assert option.issues() == ()

    def test_button(self) -> None:
        option = parse_option("option name Clear Hash type button")
        assert option is not None
        assert option.name == "Clear Hash"
        assert option.type is OptionType.BUTTON
        assert option.default is None
        assert option.issues() == ()

    def test_string(self) -> None:
        option = parse_option(r"option name NalimovPath type string default c:\ my folder")
        assert option is not None
        assert option.type is OptionType.STRING
        assert option.default == r"c:\ my folder"
        assert option.issues() == ()

    def test_empty_string_default(self) -> None:
        option = parse_option("option name BackendOptions type string default")
        assert option is not None
        assert option.default == ""
        assert option.issues() == ()

    def test_other_line(self) -> None:
        assert parse_option("info depth 1") is None

    @pytest.mark.parametrize(
        "line",
        [
            "option Hash type spin default 16",
            "option name Hash spin default 16",
            "option name type spin default 16",
            "option name Hash type",
            "option name Hash type wobble default 16",
            "option name Hash type spin default 16 min one max 1024",
            "option name Hash type spin 16",
        ],
    )
    def test_malformed(self, line: str) -> None:
        with pytest.raises(ProtocolError):
            parse_option(line)

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("option name Hash type spin default 4096 min 1 max 1024", "outside"),
            ("option name Ponder type check default yes", "true/false"),
            ("option name Style type combo default Wild var Solid", "var values"),
            ("option name Clear Hash type button default 1", "default/min/max/var"),
        ],
    )
    def test_issues_reported(self, line: str, expected: str) -> None:
        option = parse_option(line)
        assert option is not None
        assert any(expected in issue for issue in option.issues())

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("option name Hash type spin default 16", "min/max"),
            ("option name NalimovPath type string", "no default"),
        ],
    )
    def test_thin_declarations_only_warn(self, line: str, expected: str) -> None:
        option = parse_option(line)
        assert option is not None
        assert option.issues() == ()
        assert any(expected in warning for warning in option.warnings())


class TestParseInfo:
    def test_full_line(self) -> None:
        info = parse_info(
            "info depth 12 seldepth 18 multipv 1 score cp 34 nodes 10000 nps 500000 hashfull 12 "
            "tbhits 0 time 20 pv e2e4 e7e5 g1f3"
        )
        assert info is not None
        assert info.depth == 12
        assert info.multipv == 1
        assert info.nodes == 10000
        assert info.pv == ("e2e4", "e7e5", "g1f3")
        assert info.score is not None
        assert info.score.cp == 34

    def test_mate_and_bound(self) -> None:
        info = parse_info("info depth 5 score mate -3 lowerbound nodes 7")
        assert info is not None
        assert info.score is not None
        assert (info.score.mate, info.score.bound) == (-3, "lowerbound")

    def test_string_swallows_the_rest(self) -> None:
        info = parse_info("info string NNUE evaluation using nn-1111.nnue depth 4")
        assert info is not None
        assert info.string == "NNUE evaluation using nn-1111.nnue depth 4"
        assert info.depth is None

    def test_unknown_tokens_ignored(self) -> None:
        info = parse_info("info wobble 7 depth 3")
        assert info is not None
        assert info.depth == 3

    def test_other_line(self) -> None:
        assert parse_info("bestmove e2e4") is None

    @pytest.mark.parametrize(
        "line",
        ["info depth", "info depth deep", "info score cp", "info score wobble", "info pv"],
    )
    def test_malformed(self, line: str) -> None:
        with pytest.raises(ProtocolError):
            parse_info(line)


class TestParseBestmove:
    def test_plain(self) -> None:
        best = parse_bestmove("bestmove e2e4")
        assert best is not None
        assert (best.move, best.ponder, best.is_null) == ("e2e4", None, False)

    def test_with_ponder(self) -> None:
        best = parse_bestmove("bestmove e7e8q ponder a1a2")
        assert best is not None
        assert (best.move, best.ponder) == ("e7e8q", "a1a2")

    def test_null_move(self) -> None:
        best = parse_bestmove("bestmove (none)")
        assert best is not None
        assert best.is_null

    def test_other_line(self) -> None:
        assert parse_bestmove("readyok") is None

    @pytest.mark.parametrize("line", ["bestmove", "bestmove e2e4 e7e5", "bestmove e2e4 ponder"])
    def test_malformed(self, line: str) -> None:
        with pytest.raises(ProtocolError):
            parse_bestmove(line)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("e2e4", True),
        ("e7e8q", True),
        ("e7e8n", True),
        ("e7e8k", False),
        ("0000", False),
        ("e2e", False),
        ("e2e9", False),
        ("Ne4", False),
    ],
)
def test_is_lan_move(token: str, expected: bool) -> None:
    assert is_lan_move(token) is expected
