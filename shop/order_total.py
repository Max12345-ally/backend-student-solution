"""Небольшое упражнение B0 для точного подсчёта денег."""

from collections.abc import Iterable
from decimal import Decimal


class InvalidQuantityError(ValueError):
    """Количество позиции должно быть положительным."""


def calculate_total(items: Iterable[tuple[Decimal, int]]) -> Decimal:
    """Возвращает сумму ``цена × количество`` для всех позиций.

    Проверка каждого количества выполняется до вычисления итоговой суммы, поэтому
    невалидный заказ не возвращает частичный успешный результат.
    """
    positions = list(items)
    if any(quantity < 0 for _, quantity in positions):
        raise InvalidQuantityError("quantity must not be negative")
    return sum((price * quantity for price, quantity in positions), start=Decimal("0"))
