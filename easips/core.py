import easips.blocks
import easips.login_watchers
from threading import Lock
from time import time, sleep

class ProtectedService:

    def __init__(self, name: str, max_attempts: int = 10, time_period: int = 5, block_duration: int = 5):
        self.login_watcher = None
        self.block = None # block_duration
        self.failed = {}
        self.stopped = False

    def refresh(self):
        if self.stopped:
            return
        now = time()
        # Refresh blocked IPs
        self.block.refresh(refresh)
        # Delete old failed attempts
        for addr, timestamps in self.failed.items():
            self.failed[addr] = [x for x in timestamps if now - x < time_period]
        self.failed = {x: y for x, y in self.failed.items() if len(y) > 0}
        # Register new failed attempts
        for addr in self.login_watcher.get_failed_attempts():
            if addr not in self.failed.keys():
                self.failed[addr] = []
            self.failed[addr].append(now)
            if len(self.failed[addr]) >= max_attempts:
                self.block.block(addr)
                self.failed[addr] = []

    def toggleStopped(self):
        self.stopped = not self.stopped

    def get_json(self):
        return None # TODO: return list of blocked ips in json

    def die(self):
        self.login_watcher.die()
        self.block.die()


class EasIPS:

    def __init__(self):
        self.services = {}
        self.next_id = 1
        self.admin_pwd = 'EasIPS'
        self.delta_t = 0.5
        self.lock = Lock()

    def add_service(self, service: ProtectedService):
        self.services[self.next_id] = service

    def del_service(self, sid: int):
        self.services[sid].stopped = True
        self.services[sid].die()
        del self.services[sid]

    def set_admin_pwd(self, new_pwd: str):
        self.admin_pwd = new_pwd

    def get_json(self, sid: int = None):
        self.lock.acquire()
        json = self.services[sid].get_json() if sid is not None \
            else None # TODO: return list of services in json
        self.lock.release()
        return json

    def run(self):
        while True:
            for service in self.services.values():
                self.lock.acquire()
                service.iteration()
                self.lock.release()
            sleep(self.delta_t)
