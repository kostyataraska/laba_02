import argparse
import logging
import sys

from streamstats.analysis import analyze_files
from streamstats.errors import CLIConfigError, StreamStatsError
from streamstats.models import ALLOWED_LEVELS, parse_timestamp
from streamstats.parsers import available_formats
from streamstats.report import RENDERERS, save_report


def setup_logger():
    logger = logging.getLogger("streamstats")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for old_handler in logger.handlers[:]:
        logger.removeHandler(old_handler)
        old_handler.close()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    return logger


def build_parser():
    parser = argparse.ArgumentParser(
        prog="streamstats",
        description="Потоковый анализатор файлов логов.",
        epilog=(
            "примеры:\n"
            "  python -m streamstats logs.jsonl --format jsonl\n"
            "  python -m streamstats a.csv b.csv --format csv --output report.json\n"
            "  python -m streamstats logs.jsonl --format jsonl --level ERROR"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--format",required=True, help="формат входных файлов")
    parser.add_argument("--output", default=None, metavar="ФАЙЛ", help="куда сохранить отчёт (по умолчанию в консоль)")
    parser.add_argument("--report-format", default="json", help="формат отчёта")
    parser.add_argument("--skip-invalid",action="store_true",help="пропускать битые строки с предупреждением, а не останавливаться",)
    parser.add_argument("--level", action="append",help="учитывать только этот уровень (можно повторять)")
    parser.add_argument("--source", action="append", help="учитывать только этот источник (можно повторять)")
    parser.add_argument("--since", metavar="ВРЕМЯ", help="не раньше (ISO 8601, включительно)")
    parser.add_argument("--until", metavar="ВРЕМЯ", help="не позже (ISO 8601, включительно)")

    return parser

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    print(args)


def parse_bound(text, option):
    if text is None:
        return None
    try:
        return parse_timestamp(text)
    except StreamStatsError as err:
        raise CLIConfigError(f"Неверное значение {option}: {err}") from err


def main(args_list=None):
    logger = setup_logger()
    parser = build_parser()
    args = parser.parse_args(args_list)


    try:
        since = parse_bound(args.since, "--since")
        until = parse_bound(args.until, "--until")
        stats = analyze_files(
            args.inputs,
            args.format,
            args.skip_invalid,
            levels=args.level,
            sources=args.source,
            since=since,
            until=until,
        )
        text = save_report(stats, args.output, args.report_format)
        if args.output is None:
            print(text)
        return 0
    except StreamStatsError as err:
        logger.error("%s", err)
        return 2
    except OSError as err:
        logger.error("Ошибка ввода-вывода: %s", err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
