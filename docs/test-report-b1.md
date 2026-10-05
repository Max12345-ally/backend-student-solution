# Отчёт проверки B1

**Модуль:** B1 Python и HTTP  
**Дата:** 2026-10-05  
**Commit:** будет добавлен после фиксации изменений.

## Команды

```sh
make check
.venv/bin/python -m shop.http_cli list
.venv/bin/python -m shop.http_cli add --name Demo --price 100
.venv/bin/python -m shop.http_cli update --id 1 --price 120
.venv/bin/python -m shop.http_cli delete --id 1
```

## Реальные зависимости и подмены

Реальные: Python 3.13.3, httpx 0.28.1, Pydantic 2.10.6, публичный DummyJSON. В unit-тестах используется `httpx.MockTransport` для контролируемых отказов; mock не выдаётся за живой API.

| ID | Фактический результат | Доказательство | Статус |
|---|---|---|---|
| B1-T01 | GET/PUT/DELETE — 200; POST — 201 | живой прогон 2026-10-05 | Пройдено |
| B1-T02 | Пустая страница возвращает `[]`, exit 0 | тест CLI | Пройдено |
| B1-T03 | 302, 404 и 500 становятся `HttpStatusClientError` до JSON-разбора | MockTransport тест | Пройдено |
| B1-T04 | timeout и ConnectError различаются; повторов POST нет | MockTransport тест | Пройдено |
| B1-T05 | Битый JSON и неверная схема различаются | MockTransport тест | Пройдено |
| B1-T06 | Контекстный клиент закрывается | MockTransport тест | Пройдено |

`make check`: Ruff и Mypy без ошибок; Pytest — 10 passed.

## Ограничения

DummyJSON не сохраняет POST/PUT/DELETE между запросами. Отдельное ревью обнаружило неверную обработку 3xx: исправлено через `raise_for_status()` и добавлен тест; нужна повторная независимая проверка.
