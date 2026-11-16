import csv
import json
from pathlib import Path

from streamstats.errors import InvalidEventError, UnsupportedFormatError
from streamstats.models import REQUIRED_FIELDS

# Реестр: имя формата -> функция-парсер. Заполняется декоратором @register_parser.
_PARSERS = {}


def register_parser(name):
    """Декоратор: добавляет функцию-парсер в реестр под именем формата.
    Парсер принимает путь к файлу и по очереди выдаёт пары (номер_строки, запись),
    где запись - словарь с полями события или объект InvalidEventError.
    """

    def decorator(func):
        if name in _PARSERS:
            raise ValueError(f"Формат уже зарегистрирован: {name}")
        _PARSERS[name] = func
        return func

    return decorator


def available_formats():
    return sorted(_PARSERS)


@register_parser("jsonl")
def parse_jsonl(file_path):
    with Path(file_path).open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                yield line_num, InvalidEventError("Пустая строка")
                continue
            try:
                record = json.loads(text)
                yield line_num, record
            except json.JSONDecodeError:
                yield line_num, InvalidEventError("Некорректный JSON")


@register_parser("csv")
def parse_csv(file_path):
    with Path(file_path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return

        for row in reader:
            # line_num у reader - сколько строк файла прочитано.
            row_num = reader.line_num
            if None in row or None in row.values():
                yield row_num, InvalidEventError("Неверное количество столбцов в CSV")
            else:
                yield row_num, row


@register_parser("plain")
def parse_plain(file_path):
    """Свой формат: обычные текстовые логи из ноутбука.

    2026-10-07T12:00:00+03:00 INFO loader Начало чтения файла
    Первые три слова - поля, всё остальное - message.
    """
    with Path(file_path).open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                yield line_num, InvalidEventError("Пустая строка")
                continue
            parts = text.split(maxsplit=3)
            if len(parts) < len(REQUIRED_FIELDS):
                yield line_num, InvalidEventError("Ожидается: время уровень источник сообщение")
                continue
            yield line_num, dict(zip(REQUIRED_FIELDS, parts, strict=True))


def get_parser(file_path, fmt):
    try:
        parser_func = _PARSERS[fmt]
    except KeyError:
        raise UnsupportedFormatError(f"Неизвестный формат: {fmt}") from None
    return parser_func(file_path)
