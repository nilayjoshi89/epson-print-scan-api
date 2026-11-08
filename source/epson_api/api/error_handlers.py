from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from epson_api.domain import errors

STATUS_CODES: dict[type[Exception], int] = {
    errors.ScannerBusyError: 409,
    errors.ScanFailedError: 502,
    errors.PrintFailedError: 502,
    errors.QueueSetupError: 502,
    errors.UnknownModelError: 422,
    errors.UnavailableOptionError: 422,
    errors.FileTooLargeError: 413,
    errors.UnsupportedDocumentError: 415,
    errors.CommandTimeoutError: 504,
}


async def handle_domain_error(_: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=STATUS_CODES[type(error)], content={"detail": str(error)})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(errors.EpsonApiError, handle_domain_error)
