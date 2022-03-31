import subprocess
from ipaddress import ip_address
from datetime import datetime
from typing import Union


class NotFoundException(Exception):
    """
    Exception to raise when the requested object doesn't exist
    """
    pass


class InvalidSettingsException(Exception):
    """
    Exception to raise when the settings of a service are not valid, and it cannot be started
    """
    pass


def modify_ufw_rule(command: str) -> bool:
    """
    Allows empty rule such that we can use insert at index
    """
    if system_call(command):
        return True
    system_call('sudo ufw deny to any port 8888 proto tcp')
    return system_call(command)


def system_call(command: str, show_output: bool = False) -> bool:
    """
    Performs a system call using a bash command and returns True if successful (if the return code is 0)
    """
    return subprocess.run(command.split(' '), capture_output=not show_output).returncode == 0


def datetime_difference(a: datetime, b: datetime = None) -> Union[str, None]:
    """
    Returns human-readable difference between two datetimes (b defaults to now)
    """
    if a is None:
        return None
    b = b or datetime.now()
    diff = int((b - a).total_seconds())
    if diff < 0:
        return datetime_difference(b, a)
    if diff < 60:
        return f"{diff} second{'s' if diff > 1 else ''} ago"
    diff = int(diff / 60)
    if diff < 60:
        return f"{diff} minute{'s' if diff > 1 else ''} ago"
    diff = int(diff / 60)
    if diff < 24:
        return f"{diff} hour{'s' if diff > 1 else ''} ago"
    diff = int(diff / 24)
    return f"{diff} day{'s' if diff > 1 else ''} ago"


def ip_addr_is_valid(ip_addr: str) -> bool:
    """
    Returns True if the input IP address is a valid IPv4/IPv6 address
    """
    try:
        ip_address(ip_addr)
        return True
    except ValueError:
        return False
