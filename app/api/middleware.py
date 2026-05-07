import logging
from uuid import uuid4

from fastapi import FastAPI, Request, Response

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger(__name__)


def add_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        incoming_request_id = request.headers.get(REQUEST_ID_HEADER)
        if incoming_request_id and incoming_request_id.strip():
            request_id = incoming_request_id.strip()
        else:
            request_id = str(uuid4())

        request.state.request_id = request_id

        logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response
