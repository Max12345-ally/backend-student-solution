"""Типизированный HTTP-клиент учебного каталога товаров."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from types import TracebackType
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class Product(BaseModel):
    """Используемые поля ответа внешнего API."""

    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    price: Decimal


class ProductPage(BaseModel):
    """Одна страница каталога DummyJSON."""

    model_config = ConfigDict(extra="ignore")

    products: list[Product]
    total: int
    skip: int
    limit: int


class CreateProduct(BaseModel):
    """Тело POST-запроса."""

    title: str
    price: Decimal


class UpdateProduct(BaseModel):
    """Тело PUT-запроса."""

    title: str | None = None
    price: Decimal | None = None


class HttpClientError(Exception):
    """Базовая безопасная ошибка клиентского вызова."""


class HttpStatusClientError(HttpClientError):
    """Сервис вернул HTTP-статус 4xx или 5xx."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP error: {status_code}")


class ResponseJsonError(HttpClientError):
    """Тело успешного ответа не является JSON."""


class ResponseSchemaError(HttpClientError):
    """JSON не соответствует ожидаемой Pydantic-схеме."""


class RequestTimeoutError(HttpClientError):
    """Сервис не ответил до истечения timeout."""


class NetworkClientError(HttpClientError):
    """Не удалось установить или поддерживать сетевое соединение."""


class ProductClient:
    """Синхронный клиент, закрывающий соединения при выходе из ``with``."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    def __enter__(self) -> ProductClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def close(self) -> None:
        self._client.close()

    def list_products(self) -> ProductPage:
        return self._request_and_validate("GET", "/products", ProductPage)

    def create_product(self, product: CreateProduct) -> Product:
        return self._request_and_validate(
            "POST", "/products/add", Product, json=product.model_dump(mode="json")
        )

    def update_product(self, product_id: int, product: UpdateProduct) -> Product:
        return self._request_and_validate(
            "PUT",
            f"/products/{product_id}",
            Product,
            json=product.model_dump(exclude_none=True, mode="json"),
        )

    def delete_product(self, product_id: int) -> Product:
        return self._request_and_validate("DELETE", f"/products/{product_id}", Product)

    def _request_and_validate(
        self,
        method: str,
        path: str,
        model: type[ModelT],
        **request_kwargs: Any,
    ) -> ModelT:
        started_at = time.monotonic()
        status_code: int | None = None
        try:
            response = self._client.request(method, path, **request_kwargs)
            status_code = response.status_code
            if response.is_error:
                raise HttpStatusClientError(response.status_code)
            try:
                payload = response.json()
            except ValueError as error:
                raise ResponseJsonError("Response body is not valid JSON") from error
            try:
                return model.model_validate(payload)
            except ValidationError as error:
                raise ResponseSchemaError(
                    "Response JSON does not match the expected schema"
                ) from error
        except httpx.TimeoutException as error:
            raise RequestTimeoutError("Request timed out; a write may have succeeded") from error
        except httpx.HTTPError as error:
            raise NetworkClientError("Network request failed") from error
        finally:
            elapsed_ms = (time.monotonic() - started_at) * 1000
            logger.info(
                "http_request method=%s path=%s status=%s duration_ms=%.1f",
                method,
                path,
                status_code,
                elapsed_ms,
            )
