# Backend Student Solution

Решение учебного задания по бэкенду магазина электроники. Реализованы B0 и B1: воспроизводимая структура, проверки и HTTP CLI каталога товаров.

## Требования

- Python 3.13
- Git

## Первый запуск

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
make check
```

`make check` запускает линтер Ruff, строгую проверку типов Mypy и тесты Pytest.

## Упражнение B0

`shop.order_total.calculate_total` принимает позиции в формате `(Decimal("цена"), количество)`. Для `2 × 100.10` и `1 × 20.20` результат — `Decimal("220.40")`. Отрицательное количество вызывает `InvalidQuantityError`; частичный итог не возвращается.

## B1: HTTP CLI товаров

По умолчанию клиент обращается к учебному API DummyJSON с timeout 5 секунд. Базовый адрес и timeout можно изменить переменными `PUBLIC_API_BASE_URL` и `HTTP_TIMEOUT_SECONDS` либо флагами `--base-url` и `--timeout`.

```sh
.venv/bin/python -m shop.http_cli list
.venv/bin/python -m shop.http_cli add --name Demo --price 100
.venv/bin/python -m shop.http_cli update --id 1 --price 120
.venv/bin/python -m shop.http_cli delete --id 1
```

Клиент различает HTTP-ошибку, timeout, сетевую ошибку, невалидный JSON и несоответствие схеме. При успехе команда завершается с кодом 0, при ошибке — с кодом 1. POST/PUT/DELETE на DummyJSON имитируются: успешный ответ не означает, что следующее чтение увидит изменение.

## Зависимости

`pyproject.toml` описывает проект и инструменты разработки, а `requirements.lock` фиксирует точные версии для повторяемой установки. При добавлении зависимостей lock-файл должен обновляться вместе с декларацией зависимостей.
