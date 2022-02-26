from ..easips.logsniffer import *

sniffer = LogSniffer('test.txt', '([a-zA-Z]*)logout([a-zA-Z]*)')
sniffer.start()

