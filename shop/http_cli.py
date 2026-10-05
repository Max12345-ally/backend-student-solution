"""Командная строка для учебного API товаров."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from shop.http_client import CreateProduct, HttpClientError, Product, ProductClient, UpdateProduct

DEFAULT_BASE_URL = "https://dummyjson.com"
DEFAULT_TIMEOUT_SECONDS = 5.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Клиент API товаров")
    parser.add_argument("--base-url", default=os.getenv("PUBLIC_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("HTTP_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="получить страницу товаров")

    add_parser = subparsers.add_parser("add", help="создать товар")
    add_parser.add_argument("--name", "--title", dest="title", required=True)
    add_parser.add_argument("--price", required=True)

    update_parser = subparsers.add_parser("update", help="изменить товар")
    update_parser.add_argument("--id", type=int, required=True)
    update_parser.add_argument("--name", "--title", dest="title")
    update_parser.add_argument("--price")

    delete_parser = subparsers.add_parser("delete", help="удалить товар")
    delete_parser.add_argument("--id", type=int, required=True)
    return parser


def parse_price(raw_price: str) -> Decimal:
    try:
        return Decimal(raw_price)
    except InvalidOperation as error:
        raise ValueError("price must be a decimal number") from error


def print_json(data: Product | list[Product]) -> None:
    if isinstance(data, list):
        print(json.dumps([product.model_dump(mode="json") for product in data], ensure_ascii=False))
        return
    print(json.dumps(data.model_dump(mode="json"), ensure_ascii=False))


def run(arguments: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    try:
        with ProductClient(args.base_url, args.timeout) as client:
            if args.command == "list":
                page = client.list_products()
                print_json(page.products)
                return 0
            if args.command == "add":
                print_json(
                    client.create_product(
                        CreateProduct(title=args.title, price=parse_price(args.price))
                    )
                )
                return 0
            if args.command == "update":
                if args.title is None and args.price is None:
                    raise ValueError("provide --name or --price for update")
                price = parse_price(args.price) if args.price is not None else None
                print_json(
                    client.update_product(args.id, UpdateProduct(title=args.title, price=price))
                )
                return 0
            print_json(client.delete_product(args.id))
            return 0
    except (HttpClientError, ValidationError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    raise SystemExit(run())


if __name__ == "__main__":
    main()
