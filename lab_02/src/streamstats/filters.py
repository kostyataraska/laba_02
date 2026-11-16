
'''Каждая функция принимает любой итерируемый объект событий и возвращает генератор.
Ничего не читается и не проверяется, пока кто-то не начнёт обход (for / next).'''



def by_level(events, levels):
    allowed = set(levels)
    return (event for event in events if event["level"] in allowed)


def by_source(events, sources):
    allowed = set(sources)
    return (event for event in events if event["source"] in allowed)


def by_time(events, since=None, until=None):
    """Оставить события с since <= время <= until. Границы - datetime с поясом."""
    for event in events:
        if since is not None and event["dt"] < since:
            continue
        if until is not None and event["dt"] > until:
            continue
        yield event


def apply_filters(events, levels=None, sources=None, since=None, until=None):
    if levels:
        events = by_level(events, levels)
    if sources:
        events = by_source(events, sources)
    if since is not None or until is not None:
        events = by_time(events, since, until)
    return events
