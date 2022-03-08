import os
from abc import ABC, abstractmethod
from os.path import getsize
from re import compile
from typing import List


class LoginTracker (ABC):

    @abstractmethod
    def poll(self) -> list:
        """
        This method should return a list with all the IP addresses that performed
        a failed login attempt since the last call to this method.
        If an IP address has failed X times, it should appear X times in the list.
        """
        raise NotImplementedError


class LogSniffer(LoginTracker):
    """
    Detects failed login attempts by reading the log files and applying a regular expression
    """

    def __init__(self, log_path: str, log_regexes: List[str]):
        self.log_path = log_path
        self.previous_size = getsize(self.log_path)
        self.log_file = open(self.log_path, 'r')
        self.log_file.read()
        self.patterns = [compile(regex) for regex in log_regexes]

    def poll(self) -> list:
        if self.previous_size > (size := os.path.getsize(self.log_path)):
            self.log_file.close()
            self.log_file = open(self.log_path, 'r')
            self.log_file.read()
        self.previous_size = size
        while line := self.log_file.readline().strip():
            for pattern in self.patterns:
                if match := pattern.match(line):
                    if len(match.groups()) > 1:
                        for i in range(int(match.groups()[0])):
                            yield match.groups()[1]
                    else:
                        yield match.groups()[0]
                    break
