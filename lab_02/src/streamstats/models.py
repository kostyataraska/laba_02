from datetime import datetime, timezone

from streamstats.errors import InvalidEventError, InvalidTimestampError

ALLOWED_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
REQUIRED_FIELDS = ["timestamp", "level", "source", "message"]


def parse_timestamp(text):
    ''' Z на конце превращаем в "+00:00"
    время без пояса считаем UTC, чтобы его можно было сравнивать с остальными.
    '''
    if not isinstance(text, str) or text.strip() == "":
        raise InvalidTimestampError("Пустой timestamp")

    clean = text.strip()
    if clean.endswith(("Z", "z")):
        clean = clean[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(clean)
    except ValueError:
        raise InvalidTimestampError(f"Неправильный формат времени: {text}") from None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def validate_event(data):
    if not isinstance(data, dict):
        raise InvalidEventError("Событие должно быть словарем")

    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            raise InvalidEventError(f"Отсутствует поле {field}")

    ts = data["timestamp"]
    level = data["level"]
    source = data["source"]
    message = data["message"]

    if not isinstance(ts, str):
        raise InvalidTimestampError("timestamp должен быть строкой")

    if not isinstance(level, str) or not isinstance(source, str) or not isinstance(message, str):
        raise InvalidEventError("Поля должны быть строками")

    dt = parse_timestamp(ts)

    if level not in ALLOWED_LEVELS:
        raise InvalidEventError(f"Недопустимый уровень: {level}")

    if source.strip() == "":
        raise InvalidEventError("Пустой source")

    return {
        "timestamp": ts,
        "dt": dt,
        "level": level,
        "source": source,
        "message": message,
    }
