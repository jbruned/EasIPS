import time
import os
import re

class LogSniffer:
    file = None

    def __init__(self, log_location: str, log_regex: str):
        self.log_location = log_location
        self.pattern = re.compile(log_regex)

    def start(self):
        self.file = open(self.log_location, 'r')
        self.file.read()

        previous_size = os.path.getsize(self.log_location)
        while True:
            if previous_size > (size := os.path.getsize(self.log_location)):
                self.file.close()
                self.file = open(self.log_location, 'r')
                self.file.read()
                previous_size = size
                print("File emptied!")

            if (line := self.file.readline(500).strip()) and self.pattern.match(line):
                print('[NEW RELEVANT LOG DETECTED]', line)
            time.sleep(0.001)
