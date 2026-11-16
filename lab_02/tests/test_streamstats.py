import json

import pytest

from streamstats.__main__ import main
from streamstats.analysis import analyze_files
from streamstats.errors import InvalidEventError
from streamstats.parsers import parse_csv, parse_jsonl


def test_parse_jsonl(tmp_path):
    f = tmp_path / "events.jsonl"
    f.write_text(
        '{"timestamp":"2026-10-07T12:00:00+03:00","level":"INFO","source":"app","message":"Запуск"}\n',
        encoding="utf-8",
    )
    records = list(parse_jsonl(f))
    assert len(records) == 1
    line_num, data = records[0]
    assert line_num == 1
    assert data["source"] == "app"


def test_parse_csv(tmp_path):
    f = tmp_path / "events.csv"
    f.write_text(
        'timestamp,level,source,message\n'
        '2026-10-07T12:00:00+03:00,ERROR,db,"Ошибка, соединение потеряно"\n',
        encoding="utf-8",
    )
    records = list(parse_csv(f))
    assert len(records) == 1
    line_num, data = records[0]
    assert line_num == 2
    assert data["level"] == "ERROR"
    assert data["message"] == "Ошибка, соединение потеряно"


def test_empty_file(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("", encoding="utf-8")
    stats = analyze_files([f], "jsonl")
    assert stats["total_events"] == 0
    assert stats["first_timestamp"] is None
    assert stats["last_timestamp"] is None
    assert stats["top_error_sources"] == []


def test_corrupted_line_default_mode(tmp_path):
    f = tmp_path / "bad.jsonl"
    f.write_text(
        '{"timestamp":"2026-10-07T12:00:00+03:00","level":"INFO","source":"app","message":"OK"}\n'
        '{"timestamp":"НЕ_ВРЕМЯ","level":"INFO","source":"app","message":"Bad"}\n',
        encoding="utf-8",
    )
    with pytest.raises(InvalidEventError) as exc_info:
        analyze_files([f], "jsonl", skip_invalid=False)
    assert "строке 2" in str(exc_info.value)


def test_corrupted_line_skip_invalid_mode(tmp_path):
    f = tmp_path / "bad.jsonl"
    f.write_text(
        '{"timestamp":"2026-10-07T12:00:00+03:00","level":"INFO","source":"app","message":"OK 1"}\n'
        'НЕВАЛИДНЫЙ_JSON\n'
        '{"timestamp":"2026-10-07T12:05:00+03:00","level":"ERROR","source":"db","message":"OK 2"}\n',
        encoding="utf-8",
    )
    stats = analyze_files([f], "jsonl", skip_invalid=True)
    assert stats["total_events"] == 2
    assert stats["skipped_lines"] == 1
    assert stats["counts_by_level"]["INFO"] == 1
    assert stats["counts_by_level"]["ERROR"] == 1


def test_multiple_files_and_timezones(tmp_path):
    f1 = tmp_path / "part1.jsonl"
    f2 = tmp_path / "part2.jsonl"

    f1.write_text(
        '{"timestamp":"2026-10-07T12:00:00+03:00","level":"ERROR","source":"auth","message":"Fail"}\n',
        encoding="utf-8",
    )
    f2.write_text(
        '{"timestamp":"2026-10-07T08:30:00+00:00","level":"CRITICAL","source":"db","message":"Crash"}\n',
        encoding="utf-8",
    )

    stats = analyze_files([f1, f2], "jsonl")
    assert stats["total_events"] == 2
    assert stats["first_timestamp"] == "2026-10-07T08:30:00+00:00"
    assert stats["last_timestamp"] == "2026-10-07T12:00:00+03:00"
    assert len(stats["top_error_sources"]) == 2


def test_unicode_support(tmp_path):
    f = tmp_path / "unicode.csv"
    f.write_text(
        "timestamp,level,source,message\n"
        "2026-10-07T12:00:00+03:00,WARNING,модуль_загрузки,Предупреждение: файл не найден\n",
        encoding="utf-8",
    )
    stats = analyze_files([f], "csv")
    assert stats["counts_by_source"]["модуль_загрузки"] == 1


def test_cli_integration(tmp_path):
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "report.json"

    input_file.write_text(
        '{"timestamp":"2026-10-07T10:00:00+00:00","level":"ERROR","source":"api","message":"500"}\n',
        encoding="utf-8",
    )

    exit_code = main(["analyze", str(input_file), "--format", "jsonl", "--output", str(output_file)])
    assert exit_code == 0
    assert output_file.exists()

    report_data = json.loads(output_file.read_text(encoding="utf-8"))
    assert report_data["total_events"] == 1
    assert report_data["top_error_sources"] == [{"source": "api", "count": 1}]

    bad_file = tmp_path / "broken.jsonl"
    bad_file.write_text("broken_json_line\n", encoding="utf-8")
    err_code = main(["analyze", str(bad_file), "--format", "jsonl"])
    assert err_code == 2
