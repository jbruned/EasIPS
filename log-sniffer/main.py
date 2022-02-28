from logsniffer import *

joomla_log_location = "../joomla/webserver/administrator/logs/error.php"
joomla_log_testcontainer = "test.txt"
# language=regexp
sniffer = LogSniffer(joomla_log_location, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}\tINFO\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\tjoomlafailure\t.*Username.*password.*not.*match.*')
sniffer.start()

