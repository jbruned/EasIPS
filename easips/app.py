from easips.core import BackgroundIPS
from easips.gui import WebGUI
from threading import Thread
from waitress import serve
import logging

class EasIPS:

    def __init__(self):
        self.ips = BackgroundIPS()
        self.gui = WebGUI(self.ips)
        self.ips.load_db()
        #self.ips.set_db(self.gui.db)

    def run(self, web_addr_port: str = "127.0.0.1:9000"):
        try:
            logging.getLogger('waitress').setLevel(logging.ERROR)
            web_thread = Thread(target = lambda: serve(self.gui.app, listen=web_addr_port))
            web_thread.daemon = True
            web_thread.start()
            print(f"[Info] Started web interface at http://{web_addr_port}")
            self.ips.run()
        except KeyboardInterrupt:
            print("\nTerminating EasIPS...")