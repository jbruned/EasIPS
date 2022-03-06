from easips.core import BackgroundIPS
from easips.gui import WebGUI
from threading import Thread
from waitress import serve

class EasIPS:

    def __init__(self):
        self.ips = BackgroundIPS()
        self.gui = WebGUI(self.ips)
        self.ips.load_db()
        #self.ips.set_db(self.gui.db)

    def run(self):
        try:
            web_thread = Thread(target = lambda: serve(self.gui.app, host="0.0.0.0", port=80))
            web_thread.daemon = True
            web_thread.start()
            self.ips.run()
        except KeyboardInterrupt:
            print("\nTerminating EasIPS...")
