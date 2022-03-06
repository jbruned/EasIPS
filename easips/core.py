from time import time, sleep
from easips.db import ServiceSettings, LoginAttempt, BlockedIP, db
from easips.locks import SSHLock, HTAccessLock
from easips.login_trackers import LogSniffer
from datetime import datetime, timedelta
from easips.util import ip_addr_is_valid, datetime_difference
from typing import Union
from warnings import warn
import json
from sqlalchemy import desc


class ProtectedService:

    def __init__(self, settings: ServiceSettings):
        self.settings = settings
        #ServiceSettings(
            #id is auto increment by deafult
            #name = name,
            #service = service,
            #time_threshold = time_threshold,
            #max_attempts = max_attempts,
            #block_duration = block_duration or None,
            #log_path = log_path or None,
            #stopped = False
        #)
        self.login_tracker = LogSniffer  # TODO: instantiate login watcher for specified service
        self.lock = HTAccessLock()  # TODO: instantiate block for specified service
        self.KEEP_HISTORY = True  # If True, old login attempt and blocked IP are kept for history reasons

    def iteration(self, db):
        self.refresh(db)

    def persist_settings(self, db):
        if self.settings.id and ServiceSettings.query.get(self.settings.id):
            pass  # db.session.merge(self.settings)  # Update the settings
        else:
            db.session.add(self.settings)  # Insert if the service doesn't exist
        db.session.commit()
        self.settings = ServiceSettings.query.get(self.settings.id)

    def log_attempt(self, ip_addr: str, db, timestamp: Union[datetime, None] = None):
        """
        This method logs when an IP has made a login attempt. If this attempt violates the set constraints, it will be blocked.
        This method also takes care of removing the blocked addresses in due time.
        :param ip: str -> The IP address that has attempted to log in
        :param timestamp: datetime | None -> The moment at which this IP has tried to log in, and thus the moment to be considered in processing it. Defaults to current time
        """
        timestamp = timestamp or datetime.now()

        if not ip_addr_is_valid(ip):
            warn(f"[Warning] {ip} is not a valid IP address to log")
        elif self.is_blocked(ip_addr, timestamp):
            print(f"[Warning] {ip_addr} is supposed to be blocked from '{self.settings.name}' "
                  "but a login attempt has been detected")
        else:
            db.session.add(LoginAttempt(
                service_id = self.settings.id,
                ip_addr = ip_addr,
                timestamp = timestamp
            ))
            db.session.commit()  # log failed attempt

        if self.has_exceeded_attempts(ip_addr, timestamp):
            self.block(ip_addr, timestamp)

    def has_exceeded_attempts(self, ip_addr: str, timestamp: Union[datetime, None] = None) -> bool:
        """
        Checks if a certain IP needs to be blocked by looking at its recent login attempts
        """
        timestamp = timestamp or datetime.now()
        return len(LoginAttempt.query.filter(
            LoginAttempt.service_id == self.settings.id,
            LoginAttempt.ip_addr == ip_addr,
            LoginAttempt.timestamp >= timestamp - timedelta(minutes = self.settings.time_threshold)
        ).all()) >= self.settings.tries

    def block(self, ip_addr: Union[str, list], db, timestamp: Union[datetime, None] = None):
        """
        Checks if a certain IP needs to be blocked by looking at its recent login attempts. This also deletes the old ones.
        """
        timestamp = timestamp or datetime.now()
        if isinstance(ip_addr, list):
            for single_ip in ip_addr:
                self.block(single_ip, db, timestamp)
        else:
            ip_addr = ip_addr.lower()
            if not ip_addr_is_valid(ip_addr):
                warn(f"[Warning] {ip_addr} is not a valid IP address to block")
            elif self.is_blocked(ip_addr):
                obj = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                             BlockedIP.active == True).first()
                obj.blocked_at = timestamp
                #db.session.add(obj)
                db.session.commit()
                print(f"[Info] {ip_addr} was already blocked from '{self.settings.name}', time is now updated")
            elif self.lock.block(ip_addr):
                db.session.add(BlockedIP(
                    service_id = self.settings.id,
                    ip_addr = ip_addr,
                    blocked_at = timestamp,
                    active = True
                ))
                db.session.commit()
                print(f"[Info] {ip_addr} has been successfully blocked from service '{self.settings.name}'")
            else:
                print(f"[Error] {ip_addr} couldn't be blocked from service '{self.settings.name}'", file=stderr)

    def unblock(self, ip_addr: Union[str, list], db, timestamp: Union[datetime, None] = None):
        """
        This method unblocks the specified IP address from the corresponding service
        """
        timestamp = timestamp or datetime.now()
        if isinstance(ip_addr, list):
            for single_ip in ip_addr:
                self.unblock(single_ip, db, timestamp)
        else:
            ip_addr = ip_addr.lower()
            if not ip_addr_is_valid(ip_addr):
                warn(f"[Warning] {ip_addr} is not a valid IP address to unblock")
            elif not self.is_blocked(ip_addr):
                print(f"[Info] Attempted to unblock not blocked address {ip_addr} from service '{self.settings.name}'")
            elif self.lock.unblock(ip_addr):
                # BlockedIP.query.filter(BlockedIP.service_id == self.settings.id and BlockedIP.ip_addr == ip_addr).delete()
                query = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                               BlockedIP.active == True)  # .first()
                if self.KEEP_HISTORY:
                    # obj = query.first()
                    for obj in query.all():
                        obj.active = False
                        # db.session.merge(obj)
                else:
                    query.delete()
                db.session.commit()
                print(f"[Info] {ip_addr} has been successfully unblocked from service '{self.settings.name}'")
            else:
                print(f"[Error] {ip_addr} couldn't be unblocked from service '{self.settings.name}'", file=stderr)

    def is_blocked(self, ip_addr: Union[str, list]) -> Union [bool, list]:
        """
        Determines if the IP address(es) are blocked from the specified service.
        If :param moment: is provided, it will also update the time of said block to the provided moment.
        """
        if isinstance(ip_addr, list):
            return [self.is_blocked(single_ip, moment) for single_ip in ip_addr]
        ip_addr = ip_addr.lower()

        if not ip_addr_is_valid(ip_addr):
            warn(f"[Warning] {ip_addr} is not a valid IP address to check")
            return False

        return len(BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                          BlockedIP.active == True).all()) > 0

    def refresh(self, db, timestamp: Union[datetime, None] = None):
        """
        Unblocks from the service those IPs whose block duration has been reached, and blocks those that have exceeded their tries
        """
        if self.settings.stopped:
            return
        timestamp = timestamp or datetime.now()

        # Remove old login attempts that have exceeded the time threshold
        if not self.KEEP_HISTORY:
            LoginAttempt.query.filter(
                LoginAttempt.timestamp < timestamp - timedelta(minutes = self.settings.time_threshold)
            ).delete()  # remove old tries
            db.session.commit()

        # If the block isn't permanent, unblock IPs that have already exceeded the block duration
        if self.settings.block_duration:
            expired = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.active == True,
                                             BlockedIP.blocked_at < timestamp - timedelta(minutes = self.settings.block_duration))
            for e in expired.all():
                #if e.active:  # For some reason inactive IPs come out despite the BlockedIP.active == True condition ¿?¿?
                self.unblock(e.ip_addr, db, timestamp)

    def toggleStopped(self):
        ''' For the changes to be permanent, the persist_settings() method needs to be called afterwards '''
        self.settings.stopped = not self.settings.stopped

    def get_blocked_ips(self, last_24h: bool = False, historic: bool = False):
        timestamp = datetime.now()
        if historic:  # Also old IPs
            blocked_ips = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id)
        elif last_24h:
            blocked_ips = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id,
                                                 BlockedIP.blocked_at >= timestamp - timedelta(minutes = 60 * 24))
        else:  # Currently blocked IPs
            blocked_ips = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id,
                                                 BlockedIP.active == True)  #, BlockedIP.blocked_at >=
                                                 #timestamp - timedelta(minutes = self.settings.block_duration))
        return [
            {'ip_address': single_ip.ip_addr, 'blocked_at': single_ip.blocked_at, 'active': single_ip.active}
            for single_ip in blocked_ips.order_by(desc(BlockedIP.blocked_at))
        ]

    def get_last_blocked(self):
        result = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id).order_by(desc(BlockedIP.blocked_at)).first()
        return None if result is None else result.blocked_at

    def get_info(self):
        return {
            'id': self.settings.id,
            'name': self.settings.name,
            'service': self.settings.service,
            'time_threshold': self.settings.time_threshold,
            'max_attempts': self.settings.max_attempts,
            'block_duration': self.settings.block_duration,
            'log_path': self.settings.log_path,
            'web_path': self.settings.web_path,
            'stopped': self.settings.stopped,
            'blocked_now': len(self.get_blocked_ips()),
            'blocked_24h': len(self.get_blocked_ips(last_24h = True)),
            'last_blocked': datetime_difference(self.get_last_blocked())
        }

    def delete(self, db):
        LoginAttempt.query.filter(LoginAttempt.service_id == self.settings.id).delete()
        BlockedIP.query.filter(BlockedIP.service_id == self.settings.id).delete()
        ServiceSettings.query.filter(ServiceSettings.id == self.settings.id).delete()
        db.session.commit()
        self.settings = None

    _SERVICES = {
        'joomla': ['regex', HTAccessLock],
        'wordpress': ['regex', HTAccessLock],
        'ssh': ['regex', SSHLock],
        'phpmyadmin': ['regex', HTAccessLock],
        # ...
    }

    @staticmethod
    def is_service_valid(service_name: str, log_path: str = None, web_path: str = None):
        ''' Checks if the desired service is supported '''
        return service_name in ProtectedService._SERVICES.keys() and (web_path is not None
            or not ProtectedService._SERVICES[service_name][1].web_path_needed())


class NotFoundException (Exception):
    pass


class BackgroundIPS:

    def __init__(self):
        self.services = []
        #self.next_id = 1
        self.admin_pwd = 'EasIPS'
        self.delta_t = 0.5
        self.db = db

    #def set_db(self, db):
        #self.db = db

    def load_db(self):
        for s in ServiceSettings.query.all():
            self.add_service(s, new = False)

    def add_service(self, settings: ServiceSettings, new: bool = True):
        #self.settings = ServiceSettings(
            #id is auto increment by deafult
            #name = name,
            #service = service,
            #time_threshold = time_threshold,
            #max_attempts = max_attempts,
            #block_duration = block_duration or None,
            #log_path = log_path or None,
            #stopped = False
        #)
        service = ProtectedService(settings)
        self.services.append(service)
        if new:
            service.persist_settings(self.db)

    def get_service(self, service_id: int) -> ProtectedService:
        for s in self.services:
            if int(s.settings.id) == int(service_id):
                return s
        raise NotFoundException

    def del_service(self, service_id: int):
        s = self.get_service(service_id)
        s.stopped = True
        s.delete(self.db)
        self.services.remove(s)

    def get_services_info(self) -> list:
        return [s.get_info() for s in self.services]

    def set_admin_pwd(self, new_pwd: str):
        self.admin_pwd = new_pwd

    def run(self):
        while True:
            for service in self.services:
                service.iteration(self.db)
            sleep(self.delta_t)
