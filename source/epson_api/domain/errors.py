class EpsonApiError(Exception):
    pass


class ScannerBusyError(EpsonApiError):
    pass


class ScanFailedError(EpsonApiError):
    pass


class PrintFailedError(EpsonApiError):
    pass


class QueueSetupError(EpsonApiError):
    pass


class UnknownModelError(EpsonApiError):
    pass


class UnavailableOptionError(EpsonApiError):
    pass


class FileTooLargeError(EpsonApiError):
    pass


class UnsupportedDocumentError(EpsonApiError):
    pass


class CommandTimeoutError(EpsonApiError):
    pass
