from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeviceState:
    state: str | int | None = None
    reasons: list[str] = field(default_factory=list)
    accepting_jobs: bool | None = None


@dataclass(frozen=True)
class PrinterStatus:
    reachable: bool | None
    state: DeviceState = field(default_factory=DeviceState)
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class JobStatus:
    id: int | None
    name: str | None
    state: str | int | None
    reasons: list[str]


@dataclass(frozen=True)
class QueueStatus:
    name: str | None
    state: DeviceState = field(default_factory=DeviceState)
    jobs: list[JobStatus] = field(default_factory=list)


@dataclass(frozen=True)
class ScannerStatus:
    device: str
    busy: bool
    reachable: bool | None


@dataclass(frozen=True)
class DeviceStatus:
    printer: PrinterStatus
    queue: QueueStatus
    scanner: ScannerStatus
