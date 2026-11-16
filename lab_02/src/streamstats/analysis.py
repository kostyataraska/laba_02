import logging
from dataclasses import dataclass
from pathlib import Path

from streamstats.errors import CLIConfigError, InvalidEncodingError, InvalidEventError
from streamstats.filters import apply_filters
from streamstats.models import ALLOWED_LEVELS, validate_event
from streamstats.parsers import get_parser

logger = logging.getLogger("streamstats")


def sort_rule(item):
    return (-item[1], item[0])


@dataclass
class ReadCounters:
    """read_events пишет, сколько строк пропущено."""

    skipped: int = 0


def read_events(file_paths, fmt, skip_invalid=False, counters=None):
    """генерато читает файлы по очереди и выдаёт проверенные события по одному."""
    for p in file_paths:
        path = Path(p)
        if not path.is_file():
            raise CLIConfigError(f"Файл не найден: {path}")

        try:
            for line_num, raw_record in get_parser(path, fmt):
                try:
                    if isinstance(raw_record, InvalidEventError):
                        raise raw_record
                    event = validate_event(raw_record)
                except InvalidEventError as err:
                    if skip_invalid:
                        if counters is not None:
                            counters.skipped += 1
                        logger.warning("Пропущена строка %s в файле %s: %s", line_num, path, err)
                        continue
                    raise InvalidEventError(
                        f"Ошибка в файле {path} на строке {line_num}: {err}"
                    ) from err
                yield event
        except UnicodeDecodeError as err:
            raise InvalidEncodingError(f"Файл {path} не в кодировке UTF-8: {err}") from err


class StatsAccumulator:
    """Накапливает итоги, хранит счетчики, события нет."""

    def __init__(self):
        self.total = 0
        self.by_level = {lvl: 0 for lvl in ALLOWED_LEVELS}
        self.by_source = {}
        self.errors_by_source = {}
        self.first_dt = None
        self.first_ts = None
        self.last_dt = None
        self.last_ts = None

    def add(self, event):
        self.total += 1
        lvl = event["level"]
        src = event["source"]
        dt = event["dt"]

        self.by_level[lvl] += 1
        self.by_source[src] = self.by_source.get(src, 0) + 1

        if lvl in ("ERROR", "CRITICAL"):
            self.errors_by_source[src] = self.errors_by_source.get(src, 0) + 1

        if self.first_dt is None or dt < self.first_dt:
            self.first_dt = dt
            self.first_ts = event["timestamp"]
        if self.last_dt is None or dt > self.last_dt:
            self.last_dt = dt
            self.last_ts = event["timestamp"]

    def to_dict(self, skipped):
        sorted_pairs = sorted(self.errors_by_source.items(), key=sort_rule)[:5]
        return {
            "total_events": self.total,
            "skipped_lines": skipped,
            "counts_by_level": self.by_level,
            "counts_by_source": self.by_source,
            "top_error_sources": [{"source": s, "count": c} for s, c in sorted_pairs],
            "first_timestamp": self.first_ts,
            "last_timestamp": self.last_ts,
        }


def analyze_files(
    file_paths, fmt, skip_invalid=False, *, levels=None, sources=None, since=None, until=None
):
    counters = ReadCounters()
    events = read_events(file_paths, fmt, skip_invalid, counters)
    events = apply_filters(events, levels, sources, since, until)

    acc = StatsAccumulator()
    for event in events:
        acc.add(event)

    return acc.to_dict(counters.skipped)
