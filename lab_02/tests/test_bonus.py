import csv
import io
import json
from datetime import datetime, timezone

import pytest

from streamstats.__main__ import main
from streamstats.analysis import analyze_files
from streamstats.errors import (
    InvalidEncodingError,
    InvalidTimestampError,
    UnsupportedFormatError,
)
from streamstats.filters import apply_filters, by_level, by_source, by_time
from streamstats.models import parse_timestamp
from streamstats.parsers import available_formats, get_parser, register_parser
from streamstats.report import render_csv

LINES = [
    '{"timestamp":"2026-10-07T10:00:00+00:00","level":"INFO","source":"app","message":"a"}',
    '{"timestamp":"2026-10-07T11:00:00+00:00","level":"ERROR","source":"db","message":"b"}',
    '{"timestamp":"2026-10-07T12:00:00+00:00","level":"CRITICAL","source":"db","message":"c"}',
    '{"timestamp":"2026-10-07T13:00:00+00:00","level":"ERROR","source":"api","message":"d"}',
]


@pytest.fixture
def sample(tmp_path):
    f = tmp_path / "sample.jsonl"
    f.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    return f


#тесты на время
def test_naive_and_aware_timestamps_do_not_crash(tmp_path):
    f = tmp_path / "mix.jsonl"
    f.write_text(
        '{"timestamp":"2026-10-07T12:00:00","level":"INFO","source":"a","message":"m"}\n'
        '{"timestamp":"2026-10-07T12:00:00+03:00","level":"INFO","source":"a","message":"m"}\n',
        encoding="utf-8",
    )
    stats = analyze_files([f], "jsonl")
    assert stats["total_events"] == 2
    assert stats["first_timestamp"] == "2026-10-07T12:00:00+03:00"  # это 09:00 UTC


def test_z_suffix():
    assert parse_timestamp("2026-10-07T09:00:00Z") == datetime(
        2026, 10, 7, 9, 0, tzinfo=timezone.utc
    )


def test_bad_timestamp():
    with pytest.raises(InvalidTimestampError):
        parse_timestamp("вчера")





def test_filters_are_lazy():
    def source():
        yield {"level": "INFO", "source": "a", "dt": None}
        raise AssertionError("прочитано слишком много")

    filtered = by_level(source(), ["INFO"])  # обход не начат - ошибки нет
    assert next(filtered)["level"] == "INFO"


def test_filter_functions():
    events = [
        {"level": "INFO", "source": "a", "dt": parse_timestamp("2026-10-07T10:00:00Z")},
        {"level": "ERROR", "source": "b", "dt": parse_timestamp("2026-10-07T12:00:00Z")},
    ]
    assert len(list(by_level(events, ["ERROR"]))) == 1
    assert len(list(by_source(events, ["a", "b"]))) == 2
    since = parse_timestamp("2026-10-07T11:00:00Z")
    assert [e["source"] for e in by_time(events, since=since)] == ["b"]
    assert [e["source"] for e in by_time(events, until=since)] == ["a"]
    assert len(list(apply_filters(events))) == 2


def test_analyze_with_filters(sample):
    stats = analyze_files([sample], "jsonl", levels=["ERROR", "CRITICAL"], sources=["db"])
    assert stats["total_events"] == 2
    assert stats["counts_by_source"] == {"db": 2}

    stats = analyze_files(
        [sample],
        "jsonl",
        since=parse_timestamp("2026-10-07T11:00:00Z"),
        until=parse_timestamp("2026-10-07T12:00:00Z"),
    )
    assert stats["total_events"] == 2
    assert stats["first_timestamp"] == "2026-10-07T11:00:00+00:00"


def test_cli_filters(sample, capsys):
    code = main(["analyze", str(sample), "--format", "jsonl", "--level", "ERROR", "--source", "db"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["total_events"] == 1


def test_cli_bad_since(sample):
    assert main(["analyze", str(sample), "--format", "jsonl", "--since", "abc"]) == 2




# тесты парсеров
def test_registry_has_builtin_formats():
    assert {"csv", "jsonl", "plain"} <= set(available_formats())


def test_unknown_format(sample):
    with pytest.raises(UnsupportedFormatError):
        get_parser(sample, "xml")


def test_register_custom_parser(tmp_path):
    @register_parser("pipe-test")
    def parse_pipe(file_path):
        with open(file_path, encoding="utf-8") as f:
            for n, line in enumerate(f, start=1):
                ts, level, source, message = line.rstrip("\n").split("|")
                yield n, {"timestamp": ts, "level": level, "source": source, "message": message}

    f = tmp_path / "events.pipe"
    f.write_text("2026-10-07T10:00:00Z|INFO|app|hello\n", encoding="utf-8")
    assert analyze_files([f], "pipe-test")["total_events"] == 1

    with pytest.raises(ValueError):
        register_parser("pipe-test")(parse_pipe)


def test_plain_format(tmp_path):
    f = tmp_path / "app.log"
    f.write_text(
        "2026-10-07T12:00:00+03:00 INFO loader Начало чтения файла\n"
        "сломанная строка\n",
        encoding="utf-8",
    )
    stats = analyze_files([f], "plain", skip_invalid=True)
    assert stats["total_events"] == 1
    assert stats["skipped_lines"] == 1
    assert stats["counts_by_source"] == {"loader": 1}




#тесты csv отчетов
def test_csv_report(sample, tmp_path):
    out = tmp_path / "report.csv"
    code = main(
        ["analyze", str(sample), "--format", "jsonl", "--output", str(out),
         "--report-format", "csv"]
    )
    assert code == 0
    rows = list(csv.reader(io.StringIO(out.read_text(encoding="utf-8"))))
    assert rows[0] == ["section", "key", "value"]
    assert ["summary", "total_events", "4"] in rows
    assert ["top_error_source", "db", "2"] in rows


def test_csv_report_empty_stats(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("", encoding="utf-8")
    text = render_csv(analyze_files([f], "jsonl"))
    assert "summary,first_timestamp," in text





def test_bad_encoding(tmp_path):
    f = tmp_path / "bad.jsonl"
    f.write_bytes(b"\xff\xfe\n")
    with pytest.raises(InvalidEncodingError):
        analyze_files([f], "jsonl")
    assert main(["analyze", str(f), "--format", "jsonl"]) == 2


def test_multiline_csv_record_line_number(tmp_path):
    f = tmp_path / "multi.csv"
    f.write_text(
        'timestamp,level,source,message\n'
        '2026-10-07T10:00:00Z,INFO,app,"две\nстроки"\n'
        'НЕ_ВРЕМЯ,INFO,app,x\n',
        encoding="utf-8",
    )
    with pytest.raises(Exception) as exc_info:
        analyze_files([f], "csv")
    assert "строке 4" in str(exc_info.value)


def test_output_to_missing_dir_returns_2(sample, tmp_path):
    out = tmp_path / "нет_такой_папки" / "r.json"
    assert main(["analyze", str(sample), "--format", "jsonl", "--output", str(out)]) == 2
