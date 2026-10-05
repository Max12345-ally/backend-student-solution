from decimal import Decimal

import pytest

from shop.order_total import InvalidQuantityError, calculate_total


def test_calculate_total_uses_decimal_without_float_artifacts() -> None:
    result = calculate_total([(Decimal("100.10"), 2), (Decimal("20.20"), 1)])

    assert result == Decimal("220.40")


def test_calculate_total_rejects_negative_quantity_without_result() -> None:
    with pytest.raises(InvalidQuantityError, match="quantity must not be negative"):
        calculate_total([(Decimal("100.10"), 2), (Decimal("20.20"), -1)])
