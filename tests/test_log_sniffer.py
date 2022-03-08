from ..easips.logsniffer import *

joomla_log_location = "../joomla/webserver/administrator/logs/error.php"
# language=regexp
joomla_log_regex = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}\tINFO\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\tjoomlafailure\t.*Username.*password.*not.*match.*'

ssh_log_location = "../ssh/logs/auth.log"
# language=regexp
ssh_log_regex = r'^\w{3}\s\d{1,2}\s\d{2}:\d{2}:\d{2}\ssshserver.*Fail.*password.*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*'


sniffer = LogSniffer(ssh_log_location, ssh_log_regex)
sniffer.start()

