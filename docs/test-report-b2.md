# Отчёт проверки B2

**Модуль:** B2 PostgreSQL и Docker  
**Дата:** 2026-10-07

## Окружение и команды

- Python 3.13.3; PostgreSQL 16-alpine; Docker Engine 26.1.1; Docker Compose 2.27.0.
- Основные команды: `docker compose up -d postgres`, `python -m shop.cli init-db`, `python -m shop.cli seed`, `python -m shop.cli create-order ...`.

## Фактически выполнено

- PostgreSQL 16 поднят через Compose с named volume `postgres_data`.
- `init-db`, затем `seed` дважды: `30|3` товаров и покупателей, без дублей.
- `hp-001:1,kb-001:2` создал draft с total `49990.00`.
- После изменения текущей цены `hp-001` на `31000.00` у старого заказа остались `unit_price=29990.00`, `total=49990.00`.
- Инъецированный сбой после первой позиции оставил число заказов неизменным: `1 → 1`.
- После `docker compose down` и `up` без `-v` в новом контейнере остались один заказ и total `49990.00`.
- Несуществующий товар, qty `0`, отрицательная цена, дубликат SKU и повтор product_id завершились ошибками; после них в БД остались `1` заказ и `0` тестовых товаров.
- `search-products --q "' ; SELECT 1; --"` вернул `[]`; строка передана SQL-параметром и не изменила данные.
- Рендер Compose с `POSTGRES_DB=review_db`, `POSTGRES_USER=review_user`, `POSTGRES_PASSWORD=review_password` показал одинаковые новые реквизиты у `postgres` и в `DATABASE_URL` сервиса `app`.

## Ограничения

Docker daemon доступен, но среда не дала доступ к `~/.docker/buildx/current`, поэтому сборка контейнера `app` и команда `docker compose run app ...` ещё не подтверждены. Те же команды CLI проверены с хоста через `.venv` против PostgreSQL из Compose. Отдельное ревью обнаружило расходящиеся реквизиты app/Postgres; исправление ожидает повторной проверки.
