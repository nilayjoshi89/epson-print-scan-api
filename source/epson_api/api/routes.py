from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from epson_api.api.dependencies import ServicesDependency
from epson_api.api.responses import PrintResponse, StatusResponse, error_responses, status_response
from epson_api.api.schemas import PRINTER_IP_DESCRIPTION, PrinterIp, PrintForm, ScanRequest

BINARY_SCHEMA = {"schema": {"type": "string", "format": "binary"}}

router = APIRouter()


@router.post(
    "/scan",
    operation_id="scan_document",
    tags=["Scanning"],
    summary="Scan a document and return the file",
    description=(
        "Scans from the flatbed and returns the file as the response body. The server keeps no copy, so save the "
        "response. Place the original against the top-left corner of the glass. A 600 dpi full-page color PNG takes "
        "about 3 minutes and is around 50 MB, so use a client timeout of at least 10 minutes. Only one scan can run "
        "per printer. Scanning uses the real device."
    ),
    response_class=FileResponse,
    responses={
        200: {
            "description": "The scanned file, in the requested format.",
            "content": {
                "image/png": BINARY_SCHEMA,
                "image/jpeg": BINARY_SCHEMA,
                "image/tiff": BINARY_SCHEMA,
                "application/pdf": BINARY_SCHEMA,
            },
        },
        **error_responses(401, 403, 409, 422, 502, 504),
    },
)
async def scan(request: ScanRequest, services: ServicesDependency) -> FileResponse:
    path = await services.scan.scan(request.printer_ip, request.to_settings())
    return FileResponse(
        path,
        filename=f"scan.{request.format}",
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


@router.post(
    "/print",
    operation_id="print_document",
    tags=["Printing"],
    summary="Print an uploaded document",
    description=(
        "Queues a document on the printer and returns its job identifier. The print queue for an address is created "
        "on first use. Every option has a default, and options are checked against the selected model's driver. "
        "Success means the job was accepted. Use `/status` to follow unfinished jobs. Printing uses real paper and ink."
    ),
    response_model=PrintResponse,
    responses=error_responses(401, 403, 413, 415, 422, 502, 504),
)
async def print_document(form: Annotated[PrintForm, Depends()], services: ServicesDependency) -> PrintResponse:
    job_id = await services.printing.print_document(form.printer_ip, form.to_document(), form.to_settings())
    return PrintResponse(job_id=job_id)


@router.get(
    "/status",
    operation_id="get_device_status",
    tags=["Status"],
    summary="Get printer, queue and scanner status",
    description=(
        "Reports the printer's own state over IPP, its CUPS queue with unfinished jobs, and the scanner. Field names "
        "follow the IPP standard. This is read-only and uses no paper or ink. Optional printer fields appear only "
        "when the printer reports them."
    ),
    response_model=StatusResponse,
    response_model_exclude_unset=True,
    responses=error_responses(401, 403, 422),
)
async def get_status(
    printer_ip: Annotated[PrinterIp, Query(description=PRINTER_IP_DESCRIPTION)], services: ServicesDependency
) -> dict[str, Any]:
    return status_response(await services.status.status(printer_ip))
