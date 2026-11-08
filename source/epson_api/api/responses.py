from typing import Any

from pydantic import BaseModel, Field

from epson_api.domain.status import DeviceState, DeviceStatus


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable reason for the failure.")


class ValidationErrorResponse(BaseModel):
    detail: str | list[dict[str, Any]] = Field(
        description="A list of invalid fields, or a sentence when the driver doesn't offer the requested option."
    )


class PrintResponse(BaseModel):
    job_id: str = Field(
        description="CUPS job identifier. Success means CUPS accepted the job, not that the page has printed."
    )


class StateFields(BaseModel):
    printer_state: str | int | None = Field(
        alias="printer-state", description="`idle`, `processing` or `stopped`. `null` when unknown."
    )
    printer_state_reasons: list[str] = Field(
        alias="printer-state-reasons",
        description="IPP reason keywords such as `none` or `media-empty-error`.",
    )
    printer_is_accepting_jobs: bool | None = Field(
        alias="printer-is-accepting-jobs", description="Whether new jobs are accepted. `null` when unknown."
    )


class PrinterSection(StateFields):
    reachable: bool | None = Field(
        description="`true` if the printer answered over IPP, `false` if not, `null` while a scan is running."
    )
    printer_make_and_model: str | None = Field(None, alias="printer-make-and-model")
    printer_alert_description: str | None = Field(None, alias="printer-alert-description")
    marker_names: list[str] | None = Field(None, alias="marker-names", description="Ink names, when reported.")
    marker_colors: list[str] | None = Field(None, alias="marker-colors", description="Ink colors, when reported.")
    marker_levels: list[int] | None = Field(None, alias="marker-levels", description="Ink levels, when reported.")


class JobSection(BaseModel):
    job_id: int | None = Field(alias="job-id", description="Final number of the `job_id` returned by `/print`.")
    job_name: str | None = Field(alias="job-name", description="Title of the document.")
    job_state: str | int | None = Field(
        alias="job-state", description="`pending`, `pending-held`, `processing` or `processing-stopped`."
    )
    job_state_reasons: list[str] = Field(alias="job-state-reasons", description="IPP reason keywords for the job.")


class QueueSection(StateFields):
    name: str | None = Field(description="CUPS queue name. `null` until the first print to this printer.")
    jobs: list[JobSection] = Field(description="Unfinished jobs only.")


class ScannerSection(BaseModel):
    device: str = Field(description="SANE device name.")
    busy: bool = Field(description="Whether this API is currently scanning on this printer.")
    reachable: bool | None = Field(description="Whether the scanner port answered. `null` while a scan is running.")


class StatusResponse(BaseModel):
    printer: PrinterSection = Field(description="State reported by the printer itself.")
    queue: QueueSection = Field(description="State of this printer's CUPS queue.")
    scanner: ScannerSection = Field(description="State of the scanner.")


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: ERROR_RESPONSES[code] for code in codes}


ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "The `X-API-Key` header is missing or wrong."},
    403: {"model": ErrorResponse, "description": "The client address isn't in the server's `ALLOWED_IPS` list."},
    409: {"model": ErrorResponse, "description": "A scan is already running on this printer. Retry when it finishes."},
    413: {"model": ErrorResponse, "description": "The file is larger than the configured upload limit."},
    415: {"model": ErrorResponse, "description": "The file is empty or isn't a supported type."},
    422: {
        "model": ValidationErrorResponse,
        "description": "A field is invalid, or the driver doesn't offer an option.",
    },
    502: {"model": ErrorResponse, "description": "The printer, scanner or CUPS reported a failure."},
    504: {"model": ErrorResponse, "description": "The operation passed its time limit."},
}


def state_fields(state: DeviceState) -> dict[str, Any]:
    return {
        "printer-state": state.state,
        "printer-state-reasons": state.reasons,
        "printer-is-accepting-jobs": state.accepting_jobs,
    }


def status_response(status: DeviceStatus) -> dict[str, Any]:
    return {
        "printer": {
            "reachable": status.printer.reachable,
            **state_fields(status.printer.state),
            **status.printer.details,
        },
        "queue": {
            "name": status.queue.name,
            **state_fields(status.queue.state),
            "jobs": [
                {"job-id": job.id, "job-name": job.name, "job-state": job.state, "job-state-reasons": job.reasons}
                for job in status.queue.jobs
            ],
        },
        "scanner": {
            "device": status.scanner.device,
            "busy": status.scanner.busy,
            "reachable": status.scanner.reachable,
        },
    }
