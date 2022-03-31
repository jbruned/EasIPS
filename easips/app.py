import logging
from threading import Thread

from waitress import serve

from easips.core import BackgroundIPS
from easips.db import db
from easips.gui import WebGUI
from easips.log import log_info


class EasIPS:
    """
    This class contains the entire EasIPS program
    It runs both the background process and the GUI, along with the database
    """

    def __init__(self):
        """
        EasIPS constructor, instantiates the background process, the GUI, and loads the database
        """
        self.ips = BackgroundIPS(db)
        self.gui = WebGUI(self.ips, db)
        self.ips.load_db()

    def run(self, web_addr_port: str = "127.0.0.1:9000"):
        """
        Runs both the EasIPS background process and the web GUI (in separate threads)
        @param web_addr_port: The IP address and port where to listen for the web GUI
                              Accepted format is "IP:PORT", where IP can be "0.0.0.0" to listen in all interfaces
        """
        try:
            logging.getLogger('waitress').setLevel(logging.ERROR)
            web_thread = Thread(target=lambda: serve(self.gui.app, listen=web_addr_port))
            web_thread.daemon = True
            web_thread.start()
            log_info(f"Started web interface at http://{web_addr_port}")
            self.ips.run()
        except KeyboardInterrupt:
            log_info("\nTerminating EasIPS...")
