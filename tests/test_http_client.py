from __future__ import annotations

import json

import httpx
import pytest

from shop import http_cli
from shop.http_client import (
    CreateProduct,
    HttpStatusClientError,
    NetworkClientError,
    ProductClient,
    ProductPage,
    RequestTimeoutError,
    ResponseJsonError,
    ResponseSchemaError,
    UpdateProduct,
)


def product_payload(
    product_id: int = 1, title: str = "Demo", price: float = 29.99
) -> dict[str, object]:
    return {"id": product_id, "title": title, "price": price}


def make_client(handler: httpx.MockTransport) -> ProductClient:
    return ProductClient("https://example.test", transport=handler)


def test_empty_page_is_a_success_and_client_closes() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"products": [], "total": 0, "skip": 0, "limit": 20}
        )
    )
    client = make_client(transport)

    with client:
        page = client.list_products()

    assert page.products == []
    assert page.total == 0
    assert client.is_closed


@pytest.mark.parametrize("status_code", [302, 404, 500])
def test_http_errors_are_not_parsed_as_products(status_code: int) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code,
            headers={"location": "https://example.test/redirect"} if status_code == 302 else {},
            json={"message": "error"},
        )
    )

    with make_client(transport) as client, pytest.raises(HttpStatusClientError) as error:
        client.list_products()

    assert error.value.status_code == status_code


def test_malformed_json_and_schema_error_are_distinct() -> None:
    malformed_json = httpx.MockTransport(lambda request: httpx.Response(200, content=b"{invalid"))
    invalid_schema = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "products": [product_payload(price="not-a-price")],
                "total": 1,
                "skip": 0,
                "limit": 20,
            },
        )
    )

    with make_client(malformed_json) as client, pytest.raises(ResponseJsonError):
        client.list_products()
    with make_client(invalid_schema) as client, pytest.raises(ResponseSchemaError):
        client.list_products()


def test_timeout_and_connect_error_are_distinct() -> None:
    timeout = httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    connect_error = httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline"))
    )

    with make_client(timeout) as client, pytest.raises(RequestTimeoutError):
        client.list_products()
    with make_client(connect_error) as client, pytest.raises(NetworkClientError):
        client.list_products()


def test_create_update_and_delete_use_the_expected_methods_and_paths() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            201 if request.method == "POST" else 200, json=product_payload(7, "Demo", 100)
        )

    with make_client(httpx.MockTransport(handler)) as client:
        created = client.create_product(CreateProduct(title="Demo", price="100"))
        updated = client.update_product(7, UpdateProduct(price="120"))
        deleted = client.delete_product(7)

    assert [request.method for request in requests] == ["POST", "PUT", "DELETE"]
    assert [request.url.path for request in requests] == [
        "/products/add",
        "/products/7",
        "/products/7",
    ]
    assert json.loads(requests[0].content) == {"title": "Demo", "price": "100"}
    assert [created.id, updated.id, deleted.id] == [7, 7, 7]


def test_cli_returns_zero_for_an_empty_page(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class EmptyPageClient:
        def __init__(self, base_url: str, timeout: float) -> None:
            pass

        def __enter__(self) -> EmptyPageClient:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def list_products(self) -> ProductPage:
            return ProductPage(products=[], total=0, skip=0, limit=20)

    monkeypatch.setattr(http_cli, "ProductClient", EmptyPageClient)

    assert http_cli.run(["list"]) == 0
    assert capsys.readouterr().out.strip() == "[]"


def test_cli_returns_one_for_a_http_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingClient:
        def __init__(self, base_url: str, timeout: float) -> None:
            pass

        def __enter__(self) -> FailingClient:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def list_products(self) -> ProductPage:
            raise HttpStatusClientError(404)

    monkeypatch.setattr(http_cli, "ProductClient", FailingClient)

    assert http_cli.run(["list"]) == 1
    assert "HTTP error: 404" in capsys.readouterr().err
