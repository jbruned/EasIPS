import traceback
from sys import stdout, stderr

# Constants
LOG_LEVEL_NOTHING = 0
LOG_LEVEL_ERROR = 1
LOG_LEVEL_WARNING = 2
LOG_LEVEL_INFO = 3
LOG_LEVEL_DEBUG = 4

# Configurable settings
LOG_LEVEL = LOG_LEVEL_INFO
PRINT_TO_CONSOLE = True  # If false, logs are only saved in the file
LOG_FILENAME = 'easips.log'
SHOW_DEBUG = True  # Debug exceptions to the console

# Open the log file
log_file = open(LOG_FILENAME, 'a') if LOG_LEVEL > LOG_LEVEL_NOTHING else None


def _log(message: str, log_type: str = "Log", console_file=stdout):
    """
    Internal function to print and/or save logs to the log file
    @param message: message to log (string)
    @param log_type: Error/Warning/Info
    @param console_file: stdout by default, stderr can be used for errors
    """
    message = f"[{log_type}] {message}"
    print(message, file=console_file)
    log_file.write(message + '\n')
    log_file.flush()


def log_error(message: str):
    """
    Log an error to the console and/or log file (depending on LOG_LEVEL
    @param message: error message to log
    """
    if LOG_LEVEL >= LOG_LEVEL_ERROR:
        _log(message, "Error", stderr)


def log_warning(message: str):
    """
    Log a warning to the console and/or log file (depending on LOG_LEVEL
    @param message: warning message to log
    """
    if LOG_LEVEL >= LOG_LEVEL_WARNING:
        _log(message, "Warning")


def log_info(message: str):
    """
    Log an info to the console and/or log file (depending on LOG_LEVEL)
    @param message: info message to log
    """
    if LOG_LEVEL >= LOG_LEVEL_INFO:
        _log(message, "Info")


def log_debug(message: str):
    """
    Log a debug to the console and/or log file (depending on LOG_LEVEL)
    @param message: debug message to log
    """
    if LOG_LEVEL >= LOG_LEVEL_DEBUG:
        _log(message, "Debug")


def debug(exception: Exception):
    """
    Traceback an exception and show it in the console (depending on LOG_LEVEL)
    @param exception: exception to log (currently ignored, last exception is used)
    """
    if LOG_LEVEL >= LOG_LEVEL_DEBUG:
        traceback.print_exc()
