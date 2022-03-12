from sys import stdout, stderr

LOG_FILE = 'easips.log'


def _log(message: str, log_type: str = "Log", file=stdout):
    print(f"[{log_type}] {message}", file=file)


def log_error(message):
    _log(message, "Error", stderr)


def log_info(message):
    _log(message, "Info")


def log_warning(message):
    _log(message, "Warning")
