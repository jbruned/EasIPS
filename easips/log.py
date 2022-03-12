import traceback
from sys import stdout, stderr


# Constants
LOG_LEVEL_NOTHING = 0
LOG_LEVEL_ERROR = 1
LOG_LEVEL_WARNING = 2
LOG_LEVEL_INFO = 3
LOG_LEVEL_DEBUG = 4

# Configurable settings
LOG_FILENAME = 'easips.log'
LOG_LEVEL = LOG_LEVEL_INFO
SHOW_DEBUG = True


log_file = open(LOG_FILENAME, 'a') if LOG_LEVEL > LOG_LEVEL_NOTHING else None


def _log(message: str, log_type: str = "Log", file=stdout):
    message = f"[{log_type}] {message}"
    print(message, file=file)
    log_file.write(message + '\n')
    log_file.flush()


def log_error(message):
    if LOG_LEVEL >= LOG_LEVEL_ERROR:
        _log(message, "Error", stderr)


def log_warning(message):
    if LOG_LEVEL >= LOG_LEVEL_WARNING:
        _log(message, "Warning")


def log_info(message):
    if LOG_LEVEL >= LOG_LEVEL_INFO:
        _log(message, "Info")


def debug(exception):
    if LOG_LEVEL >= LOG_LEVEL_DEBUG:
        traceback.print_exc()
        # print(exception, stderr)
