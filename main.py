from easips.core import EasIPS
from easips.gui import app
from threading import Thread

ips = EasIPS()

web_thread = Thread(target=app.run)
web_thread.daemon = True

try:
    web_thread.start()
    ips.run()
except KeyboardInterrupt:
    print("\nTerminating EasIPS...")
