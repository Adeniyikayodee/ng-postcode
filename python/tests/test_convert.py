from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import httpx
import pytest

from ng_postcode import Postcode
from ng_postcode.convert import Converted, convert, main, nipost, read, rows, write


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ek 01 a03 fk 01", Converted("EK01A03FK01", "valid", "", "")),
        ("EK-O1-A03-FK-01", Converted("", "suggested", "EK-01-A03-FK-01", "invalid lga segment")),
        ("360001", Converted("", "invalid", "", "expected 11 letters and digits, found 6")),
        ("  ", Converted("", "empty", "", "")),
    ],
)
def test_a_cell_is_valid_suggested_invalid_or_empty(text: str, expected: Converted) -> None:
    assert convert(text) == expected


def test_a_suggestion_is_never_written_as_the_code() -> None:
    (row,) = rows([{"pc": "EK-O1-A03-FK-01"}], "pc", None)
    assert (row["pc_compact"], row["pc_suggestion"]) == ("", "EK-01-A03-FK-01")


def test_converts_a_file_and_reports_the_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, target = tmp_path / "in.csv", tmp_path / "out.csv"
    # A byte order mark, as a spreadsheet export begins with.
    source.write_text(
        "﻿id,pc\n1,ek 01 a03 fk 01\n2,EK-O1-A03-FK-01\n3,360001\n4,\n", encoding="utf-8"
    )
    main([str(source), "--column", "pc", "--out", str(target)])
    written = list(csv.DictReader(target.open(encoding="utf-8")))
    assert [row["pc_status"] for row in written] == ["valid", "suggested", "invalid", "empty"]
    assert written[0] == {
        "id": "1",
        "pc": "ek 01 a03 fk 01",
        "pc_compact": "EK01A03FK01",
        "pc_status": "valid",
        "pc_suggestion": "",
        "pc_error": "",
    }
    assert "4 rows: 1 valid, 1 suggested, 1 invalid, 1 empty" in capsys.readouterr().err


def test_a_missing_column_or_key_stops_before_anything_is_written(tmp_path: Path) -> None:
    source, target = tmp_path / "in.csv", tmp_path / "out.csv"
    source.write_text("id,pc\n1,x\n", encoding="utf-8")
    target.write_text("kept", encoding="utf-8")
    with pytest.raises(SystemExit, match="no column named 'postcode'"):
        read(io.StringIO("id,pc\n1,x\n"), "postcode")
    with pytest.raises(SystemExit, match="no column named 'postcode'"):
        main([str(source), "--column", "postcode", "--out", str(target)])
    with pytest.raises(SystemExit):
        main([str(source), "--column", "pc", "--confirm"])
    assert target.read_text(encoding="utf-8") == "kept"


def test_the_input_file_is_never_written_over(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("id,pc\n1,EK01A03FK01\n", encoding="utf-8")
    link = tmp_path / "link.csv"
    link.symlink_to(source)
    for out in (source, link):
        with pytest.raises(SystemExit, match="--out is the input file"):
            main([str(source), "--column", "pc", "--out", str(out)])
    assert source.read_text(encoding="utf-8") == "id,pc\n1,EK01A03FK01\n"


def test_a_file_with_no_rows_keeps_its_header(tmp_path: Path) -> None:
    source, target = tmp_path / "in.csv", tmp_path / "out.csv"
    source.write_text("id,pc\n", encoding="utf-8")
    main([str(source), "--column", "pc", "--out", str(target)])
    assert target.read_text(encoding="utf-8") == (
        "id,pc,pc_compact,pc_status,pc_suggestion,pc_error\n"
    )


def test_a_row_longer_than_the_header_stops_the_run(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("id,pc\n1,EK01A03FK01\n2,x,extra\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="line 3 has more cells than the header"):
        main([str(source), "--column", "pc", "--out", str(tmp_path / "out.csv")])


def test_a_row_shorter_than_the_header_is_empty(capsys: pytest.CaptureFixture[str]) -> None:
    write(read(io.StringIO("id,pc\n1\n"), "pc"), sys.stdout, "pc", None)
    assert capsys.readouterr().out.splitlines()[1] == "1,,,empty,,"


def test_a_column_the_run_would_add_is_never_replaced() -> None:
    with pytest.raises(SystemExit, match="already has a column named 'pc_status'"):
        read(io.StringIO("pc,pc_status\nEK01A03FK01,shipped\n"), "pc")


def test_a_header_that_repeats_a_name_is_refused() -> None:
    with pytest.raises(SystemExit, match="names 'id' more than once"):
        read(io.StringIO("id,pc,id\n1,EK01A03FK01,2\n"), "pc")


def test_a_file_that_cannot_be_read_is_reported_in_one_line(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match=r"ng-postcode: .*No such file"):
        main([str(tmp_path / "missing.csv"), "--column", "pc"])
    latin = tmp_path / "latin.csv"
    latin.write_bytes("id,pc\n1,caf\xe9\n".encode("latin-1"))
    with pytest.raises(SystemExit, match="is not UTF-8"):
        main([str(latin), "--column", "pc"])


def test_confirming_asks_once_for_each_code_and_stops_at_the_first_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        code = request.url.params["code"]
        asked.append(code)
        if code == "LA-11-W06-TC-10":
            error = {"code": "rate_limited", "message": "slow down"}
            return httpx.Response(429, json={"error": error})
        return httpx.Response(
            200, json={"data": {"postcode": code, "valid": code.startswith("EK")}}
        )

    real = httpx.Client
    stub = httpx.MockTransport(handle)
    monkeypatch.setattr(httpx, "Client", lambda **options: real(transport=stub, **options))
    cells = ["EK01A03FK01", "ek-01-a03-fk-01", "FC03B06AG12", "LA11W06TC10", "EK01A03ZZ14", "x"]
    out = list(rows(({"pc": cell} for cell in cells), "pc", nipost("key")))
    assert [row["pc_assigned"] for row in out] == ["true", "true", "false", "", "", ""]
    assert asked == ["EK-01-A03-FK-01", "FC-03-B06-AG-12", "LA-11-W06-TC-10"]
    assert Postcode("EK01A03FK01").compact == out[0]["pc_compact"]
