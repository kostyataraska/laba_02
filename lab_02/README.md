# Лабораторная работа №2. Потоковый анализатор файлов (streamstats)

Программа для построчного чтения файлов логов в форматах CSV и JSONL. Собирает статистику по событиям без полной загрузки файлов в оперативную память и сохраняет итоговый отчёт в формате JSON.

## Что считает программа

- Общее количество корректных событий (`total_events`) и число пропущенных строк (`skipped_lines`).
- Количество событий по каждому уровню важности (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- Количество событий по каждому источнику (`source`).
- Топ-5 источников по числу ошибок уровней `ERROR` и `CRITICAL`.
- Временные метки первого и последнего события с учётом часовых поясов (формат ISO 8601).

## Формат входных данных

Каждая запись в файле должна содержать четыре обязательных поля:
- `timestamp` — дата и время в формате ISO 8601 (например, `2026-10-07T12:00:00+03:00`);
- `level` — уровень события (`DEBUG`, `INFO`, `WARNING`, `ERROR` или `CRITICAL`);
- `source` — источник события (непустая строка);
- `message` — текст сообщения.

## Подключение виртуального окружения 
Если виртуальное окружение не установлено в корневой папке, установите командой:
```bash
python -m venv .venv
```
Актвируйте виртуальное окружение.
```bash
.venv\Scripts\activate
```
## Установка

В виртуальном окружении установите пакет из корневой папки
```bash
pip install -e .
```

## Запуск из командной строки

Анализ одного или нескольких файлов с сохранением результата в файл:
```bash
python -m streamstats analyze data1.jsonl data2.jsonl --format jsonl --output report.json
```

Анализ CSV-файла с выводом отчёта прямо в консоль (без указания `--output`):
```bash
python -m streamstats analyze logs.csv --format csv
```

Режим `--skip-invalid` (битые строки не останавливают программу, а пропускаются с выводом предупреждения `WARNING` в лог):
```bash
python -m streamstats analyze logs.jsonl --format jsonl --skip-invalid --output report.json
```

По умолчанию (без флага `--skip-invalid`) при обнаружении некорректной строки программа останавливается, выводит сообщение с номером строки и завершается с кодом `2`.

## Фильтры (ленивые)

Фильтры применяются до подсчёта статистики, события читаются потоком и в память не складываются:
```bash
python -m streamstats analyze logs.jsonl --format jsonl --level ERROR --level CRITICAL
python -m streamstats analyze logs.jsonl --format jsonl --source db --since 2026-10-07T10:00:00+00:00 --until 2026-10-07T12:00:00+00:00
```
`--level` и `--source` можно повторять. Границы `--since` / `--until` включительные. Время без часового пояса считается UTC.

## Свои форматы (реестр парсеров)

Формат добавляется функцией-генератором с декоратором, менять остальной код не нужно:
```python
from streamstats.parsers import register_parser

@register_parser("pipe")
def parse_pipe(file_path):
    ...  # yield номер_строки, словарь_события
```
Встроенные форматы: `csv`, `jsonl`, `plain` (строки вида `2026-10-07T12:00:00+03:00 INFO loader Текст`).

## Отчёт в CSV

```bash
python -m streamstats analyze logs.jsonl --format jsonl --report-format csv --output report.csv
```
Таблица из столбцов `section,key,value` строится из того же словаря статистики, что и JSON.

## Структура проекта

- `src/streamstats/errors.py` — классы пользовательских исключений.
- `src/streamstats/models.py` — проверка полей события и разбор времени.
- `src/streamstats/parsers.py` — генераторы для построчного чтения CSV и JSONL.
- `src/streamstats/analysis.py` — основной цикл подсчёта статистики по файлам.
- `src/streamstats/filters.py` — ленивые фильтры по уровню, источнику и времени.
- `src/streamstats/report.py` — формирование и сохранение отчёта (JSON или CSV).
- `src/streamstats/__main__.py` — обработка аргументов командной строки (CLI) и настройка логгера.
- `tests/test_streamstats.py`, `tests/test_bonus.py` — модульные и интеграционные тесты.

## Проверка и запуск тестов

Проверка и запуск тестов выполняются в виртуальном окружении

```bash
python -m pytest
ruff check .
python -m streamstats --help
```
