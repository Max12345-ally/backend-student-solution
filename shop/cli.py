"""B2 CLI: PostgreSQL without an ORM."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql://shop:shop@localhost:5433/shop"


class ShopError(Exception):
    """Expected domain or database command error."""


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def money(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ShopError("price must be a decimal") from error
    if result < 0 or result > Decimal("9999999999.99"):
        raise ShopError("price is out of range")
    return result.quantize(Decimal("0.01"))


def connect() -> psycopg.Connection[Any]:
    try:
        return psycopg.connect(database_url(), row_factory=dict_row)
    except psycopg.OperationalError as error:
        raise ShopError("database connection failed") from error


def init_db() -> None:
    with connect() as connection:
        connection.execute((ROOT / "sql/schema.sql").read_text())


def seed() -> None:
    products = json.loads((ROOT / "data/catalog/products.json").read_text())
    customers = json.loads((ROOT / "data/customers/customers.json").read_text())
    with connect() as connection:
        for product in products:
            connection.execute(
                """INSERT INTO products (id, sku, name, category, description, attributes, purpose_tags, price, currency, in_stock)
                VALUES (%(id)s, %(sku)s, %(name)s, %(category)s, %(description)s, %(attributes)s::jsonb, %(purpose_tags)s, %(price)s, %(currency)s, %(in_stock)s)
                ON CONFLICT (id) DO UPDATE SET sku = EXCLUDED.sku, name = EXCLUDED.name, category = EXCLUDED.category,
                description = EXCLUDED.description, attributes = EXCLUDED.attributes, purpose_tags = EXCLUDED.purpose_tags,
                price = EXCLUDED.price, currency = EXCLUDED.currency, in_stock = EXCLUDED.in_stock""",
                {**product, "attributes": json.dumps(product["attributes"])},
            )
        for customer in customers:
            connection.execute(
                """INSERT INTO customers (id, name, contact) VALUES (%(id)s, %(name)s, %(contact)s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, contact = EXCLUDED.contact""",
                customer,
            )


def add_product(product_id: str, sku: str, name: str, category: str, price: str) -> None:
    if category not in {"headphones", "laptops", "keyboards", "monitors"}:
        raise ShopError("unknown category")
    with connect() as connection:
        try:
            connection.execute(
                """INSERT INTO products (id, sku, name, category, description, price, in_stock)
                VALUES (%s, %s, %s, %s, %s, %s, true)""",
                (product_id, sku, name, category, "Added by B2 CLI", money(price)),
            )
        except psycopg.errors.UniqueViolation as error:
            raise ShopError("product id or SKU already exists") from error


def update_price(product_id: str, price: str) -> None:
    with connect() as connection:
        result = connection.execute(
            "UPDATE products SET price = %s WHERE id = %s", (money(price), product_id)
        )
        if result.rowcount != 1:
            raise ShopError("product not found")


def add_customer(customer_id: str, name: str, contact: str) -> None:
    with connect() as connection:
        try:
            connection.execute(
                "INSERT INTO customers (id, name, contact) VALUES (%s, %s, %s)",
                (customer_id, name, contact),
            )
        except psycopg.errors.UniqueViolation as error:
            raise ShopError("customer id already exists") from error


def get_product(product_id: str) -> dict[str, Any]:
    with connect() as connection:
        product = connection.execute(
            "SELECT * FROM products WHERE id = %s", (product_id,)
        ).fetchone()
    if product is None:
        raise ShopError("product not found")
    return {**product, "price": f"{product['price']:.2f}"}


def parse_items(raw_items: str) -> list[tuple[str, int]]:
    parsed: list[tuple[str, int]] = []
    seen: set[str] = set()
    for raw_item in raw_items.split(","):
        product_id, separator, raw_quantity = raw_item.partition(":")
        if not separator or not product_id or not raw_quantity.isdigit():
            raise ShopError("items must have product_id:quantity format")
        quantity = int(raw_quantity)
        if quantity < 1 or quantity > 99:
            raise ShopError("quantity must be between 1 and 99")
        if product_id in seen:
            raise ShopError("duplicate product_id")
        seen.add(product_id)
        parsed.append((product_id, quantity))
    if not 1 <= len(parsed) <= 20:
        raise ShopError("an order needs 1 to 20 different products")
    return parsed


def create_order(
    customer_id: str, items: list[tuple[str, int]], fail_after_first_item: bool = False
) -> dict[str, Any]:
    with connect() as connection:
        customer = connection.execute(
            "SELECT id FROM customers WHERE id = %s", (customer_id,)
        ).fetchone()
        if customer is None:
            raise ShopError("customer not found")
        product_rows: list[dict[str, Any]] = []
        for product_id, quantity in items:
            product = connection.execute(
                "SELECT id, price, currency, in_stock FROM products WHERE id = %s", (product_id,)
            ).fetchone()
            if product is None:
                raise ShopError(f"product not found: {product_id}")
            if not product["in_stock"]:
                raise ShopError(f"product unavailable: {product_id}")
            product_rows.append({**product, "quantity": quantity})
        total = sum((row["price"] * row["quantity"] for row in product_rows), Decimal("0.00"))
        order_id = uuid.uuid4()
        with connection.transaction():
            connection.execute(
                "INSERT INTO orders (id, customer_id, status, total) VALUES (%s, %s, 'draft', %s)",
                (order_id, customer_id, total),
            )
            for index, row in enumerate(product_rows):
                line_total = row["price"] * row["quantity"]
                connection.execute(
                    """INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (order_id, row["id"], row["quantity"], row["price"], line_total),
                )
                if fail_after_first_item and index == 0:
                    raise ShopError("injected failure after first item")
        return {"id": str(order_id), "status": "draft", "total": f"{total:.2f}"}


def show_order(order_id: str) -> dict[str, Any]:
    with connect() as connection:
        order = connection.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
        if order is None:
            raise ShopError("order not found")
        items = connection.execute(
            "SELECT product_id, quantity, unit_price, line_total FROM order_items WHERE order_id = %s ORDER BY product_id",
            (order_id,),
        ).fetchall()
    return {**order, "id": str(order["id"]), "total": f"{order['total']:.2f}", "items": items}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SQL CLI магазина")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db")
    commands.add_parser("seed")
    add_product_parser = commands.add_parser("add-product")
    add_product_parser.add_argument("--id", required=True)
    add_product_parser.add_argument("--sku", required=True)
    add_product_parser.add_argument("--name", required=True)
    add_product_parser.add_argument("--category", required=True)
    add_product_parser.add_argument("--price", required=True)
    update_price_parser = commands.add_parser("update-price")
    update_price_parser.add_argument("--id", required=True)
    update_price_parser.add_argument("--price", required=True)
    add_customer_parser = commands.add_parser("add-customer")
    add_customer_parser.add_argument("--id", required=True)
    add_customer_parser.add_argument("--name", required=True)
    add_customer_parser.add_argument("--contact", required=True)
    get_product_parser = commands.add_parser("get-product")
    get_product_parser.add_argument("--id", required=True)
    create = commands.add_parser("create-order")
    create.add_argument("--customer", required=True)
    create.add_argument("--items", required=True)
    create.add_argument("--fail-after-first-item", action="store_true")
    show = commands.add_parser("show-order")
    show.add_argument("--id", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "init-db":
            init_db()
            print("schema initialized")
        elif args.command == "seed":
            seed()
            print("seed loaded")
        elif args.command == "add-product":
            add_product(args.id, args.sku, args.name, args.category, args.price)
            print("product added")
        elif args.command == "update-price":
            update_price(args.id, args.price)
            print("price updated")
        elif args.command == "add-customer":
            add_customer(args.id, args.name, args.contact)
            print("customer added")
        elif args.command == "get-product":
            print(json.dumps(get_product(args.id), default=str))
        elif args.command == "create-order":
            print(
                json.dumps(
                    create_order(args.customer, parse_items(args.items), args.fail_after_first_item)
                )
            )
        else:
            print(json.dumps(show_order(args.id), default=str))
    except ShopError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
