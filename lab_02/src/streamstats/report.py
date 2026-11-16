import csv
import json
from io import StringIO
from pathlib import Path


def render_json(stats):
    return json.dumps(stats, ensure_ascii=False, indent=2)


def render_csv(stats):
    """словарь stats, развёрнутый в длинную таблицу(section,key,value)."""
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["section", "key", "value"])

    for key in ("total_events", "skipped_lines", "first_timestamp", "last_timestamp"):
        value = stats[key]
        writer.writerow(["summary", key, "" if value is None else value])

    for level, count in stats["counts_by_level"].items():
        writer.writerow(["level", level, count])
    for source, count in stats["counts_by_source"].items():
        writer.writerow(["source", source, count])
    for item in stats["top_error_sources"]:
        writer.writerow(["top_error_source", item["source"], item["count"]])

    return buffer.getvalue()


RENDERERS = {"json": render_json, "csv": render_csv}


def save_report(stats, output_path=None, fmt="json"):
    text = RENDERERS[fmt](stats)

    if output_path is not None:
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(text)

    return text
