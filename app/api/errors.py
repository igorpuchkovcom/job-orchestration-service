import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from app.api.schemas.errors import ApiError

HTTP_STATUS_CODE_TO_ERROR_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
}

REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger(__name__)


def make_api_error(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return ApiError(code=code, message=message, details=details).model_dump()


def _normalize_http_exception(exc: HTTPException) -> ApiError:
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code")
        message = exc.detail.get("message")
        if isinstance(code, str) and isinstance(message, str):
            return ApiError(
                code=code,
                message=message,
                details=exc.detail.get("details"),
            )

    if isinstance(exc.detail, str):
        return ApiError(
            code=HTTP_STATUS_CODE_TO_ERROR_CODE.get(exc.status_code, "http_error"),
            message=exc.detail,
        )

    return ApiError(
        code=HTTP_STATUS_CODE_TO_ERROR_CODE.get(exc.status_code, "http_error"),
        message="Request failed.",
        details=exc.detail,
    )


def _get_request_id(request: Request) -> str | None:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id.strip():
        return request_id
    return None


def _set_request_id_header(response: JSONResponse, request_id: str | None) -> JSONResponse:
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    payload = _normalize_http_exception(exc)
    response = JSONResponse(status_code=exc.status_code, content=payload.model_dump())
    return _set_request_id_header(response, _get_request_id(request))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    payload = ApiError(
        code="validation_error",
        message="Request validation failed.",
        details=exc.errors(),
    )
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=payload.model_dump(),
    )
    return _set_request_id_header(response, _get_request_id(request))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.exception(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    payload = ApiError(
        code="internal_error",
        message="Internal server error.",
        details={"request_id": request_id or "unknown"},
    )
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload.model_dump(),
    )
    return _set_request_id_header(response, request_id)
