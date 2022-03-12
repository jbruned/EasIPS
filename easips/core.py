from datetime import datetime, timedelta
from time import sleep, time
from typing import Union
from warnings import warn
from sys import stderr

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

from easips.db import ServiceSettings, LoginAttempt, BlockedIP
from easips.locks import ServiceLock, HTAccessLock, FirewallLock, EtcHostsLock
from easips.login_trackers import LoginTracker, LogSniffer
from easips.util import ip_addr_is_valid, datetime_difference, InvalidSettingsException, NotFoundException


class ProtectedService:

    settings: Union[ServiceSettings, None]
    login_tracker: Union[LoginTracker, None]
    lock: Union[ServiceLock, None]
    modified: bool

    def __init__(self, settings: ServiceSettings):
        """
        ProtectedService's constructor
        """
        self.settings = settings
        self.login_tracker = None
        self.lock = None
        self.modified = False

    def _get_lock(self):
        """
        Gets the appropriate ServiceLock based on the service settings
        """
        if self.settings.path.isNumeric():
            self.lock = FirewallLock(int(self.settings.path))
        elif '/' in self.settings.path:
            self.lock = HTAccessLock(self.settings.path)
        else:
            self.lock = EtcHostsLock(self.settings.path)

    _REGEX_LIST = {  # service_name: list_of_regex
        'joomla': [
            # Detect joomla in error log
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}\tINFO\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\tjoomlafailure\t.*Username.*password.*not.*match.*'
        ],
        'wordpress': [
            # Detect specific apache log lines
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*POST\s/wp-login\.php.*\s200\s\d+.*'
        ],
        'ssh': [
            # Detect in log from rsyslog
            r'^\w{3}\s*\d{1,2}\s\d{2}:\d{2}:\d{2}\ssshserver.*repeated\s(\d+)\stimes.*Fail.*password.*\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*',
            r'^\w{3}\s*\d{1,2}\s\d{2}:\d{2}:\d{2}\ssshserver.*Fail.*password.*\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*',
        ],
        'phpmyadmin': [
            # Detect specific apache log lines
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*POST\s/index\.php.*\s200\s\d+.*'
        ]
    }

    def _get_tracker(self):
        """
        Gets the appropriate LoginTracker based on the service settings
        """
        self.login_tracker = LogSniffer(self.settings.log_path, self._REGEX_LIST[self.settings.type])

    def init_components(self):
        """
        Initializes both the LoginTracker and the Lock or raises an InvalidSettingsException
        """
        try:
            self._get_tracker()
            self._get_lock()
        except:
            self.login_tracker = None
            self.lock = None
            if not self.settings.stopped:
                self.toggle_stopped(True)
            print(f"[Error] Couldn't initialize service '{self.settings.name}', thus it has been stopped", file=stderr)
            raise InvalidSettingsException

    def are_components_initialized(self) -> bool:
        """
        Returns True if the LoginTracker and the Lock are initialized
        """
        return self.login_tracker is not None and self.lock is not None

    def iteration(self, db: SQLAlchemy):
        """
        Method which should be called constantly from the main loop
        """
        if self.modified:
            self.persist_settings(db)
        if self.settings.stopped:
            return
        if not self.are_components_initialized():
            try:
                self.init_components()
            except InvalidSettingsException:
                self.toggle_stopped(True)
                self.persist_settings(db)
        if self.are_components_initialized():
            self.refresh(db)
            for ip_addr in self.login_tracker.poll():
                self.log_attempt(ip_addr, db)

    def flag_as_modified(self):
        """
        Flag the service's settings as modified to add/update them to the database
        Raises an InvalidSettingsException if it detects that the ServiceSettings are not valid
        """
        self.modified = True
        self.init_components()

    def persist_settings(self, db: SQLAlchemy):  # , force: bool = True):
        """
        Add or update the settings of this service to database
        """
        # if not force and not db.session.is_modified(self.settings):
        #     return
        if self.settings.id and ServiceSettings.query.get(self.settings.id):
            pass  # db.session.merge(self.settings)  # Update the settings
        else:
            db.session.add(self.settings)  # Insert if the service doesn't exist
        db.session.commit()
        self.modified = False
        # self.settings = ServiceSettings.query.get(self.settings.id)

    def log_attempt(self, ip_addr: str, db: SQLAlchemy, timestamp: Union[datetime, None] = None):
        """
        This method logs when an IP has made a login attempt. If it violates the set constraints, it will be blocked.
        This method also takes care of removing the blocked addresses in due time.
        :param ip_addr: str -> The IP address that has attempted to log in
        :param db: database instance.
        :param timestamp: datetime | None -> The moment at which this IP has tried to log in, and thus the moment to be
                                             considered in processing it. Defaults to current time
        """
        timestamp = timestamp or datetime.now()

        if not ip_addr_is_valid(ip_addr):
            print(f"[Warning] {ip_addr} is not a valid IP address to log")
        elif self.is_blocked(ip_addr):
            print(f"[Warning] {ip_addr} is supposed to be blocked from '{self.settings.name}' "
                  "but a login attempt has been detected")
        else:
            db.session.add(LoginAttempt(
                service_id=self.settings.id,
                ip_addr=ip_addr,
                timestamp=timestamp
            ))
            db.session.commit()  # Log failed attempt

        if self.has_exceeded_attempts(ip_addr, timestamp):
            self.block(ip_addr, db, timestamp)

    def has_exceeded_attempts(self, ip_addr: str, timestamp: Union[datetime, None] = None) -> bool:
        """
        Checks if a certain IP needs to be blocked by looking at its recent login attempts
        """
        timestamp = timestamp or datetime.now()
        return len(LoginAttempt.query.filter(
            LoginAttempt.service_id == self.settings.id,
            LoginAttempt.ip_addr == ip_addr,
            LoginAttempt.timestamp >= timestamp - timedelta(minutes=self.settings.time_threshold)
        ).all()) >= self.settings.max_attempts

    def block(self, ip_addr: Union[str, list], db: SQLAlchemy, timestamp: Union[datetime, None] = None):
        """
        Checks if a certain IP needs to be blocked by looking at its recent login attempts.
        """
        timestamp = timestamp or datetime.now()
        if isinstance(ip_addr, list):
            for single_ip in ip_addr:
                self.block(single_ip, db, timestamp)
        else:
            ip_addr = ip_addr.lower()
            if not ip_addr_is_valid(ip_addr):
                print(f"[Warning] {ip_addr} is not a valid IP address to block")
            elif self.is_blocked(ip_addr):
                obj = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                             BlockedIP.active).first()
                obj.blocked_at = timestamp
                # db.session.add(obj)
                db.session.commit()
                print(f"[Info] {ip_addr} was already blocked from '{self.settings.name}', time is now updated")
            elif self.lock.block(ip_addr):
                db.session.add(BlockedIP(
                    service_id=self.settings.id,
                    ip_addr=ip_addr,
                    blocked_at=timestamp,
                    active=True
                ))
                db.session.commit()
                print(f"[Info] {ip_addr} has been successfully blocked from service '{self.settings.name}'")
            else:
                print(f"[Error] {ip_addr} couldn't be blocked from service '{self.settings.name}'", file=stderr)

    def unblock(self, ip_addr: Union[str, list], db: SQLAlchemy, timestamp: Union[datetime, None] = None):
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
                query = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                               BlockedIP.active)
                for obj in query.all():
                    obj.active = False
                db.session.commit()
                print(f"[Info] {ip_addr} has been successfully unblocked from service '{self.settings.name}'")
            else:
                print(f"[Error] {ip_addr} couldn't be unblocked from service '{self.settings.name}'", file=stderr)

    def is_blocked(self, ip_addr: Union[str, list]) -> Union[bool, list]:
        """
        Determines if the IP address(es) are blocked from the specified service.
        If :param moment: is provided, it will also update the time of said block to the provided moment.
        """
        if isinstance(ip_addr, list):
            return [self.is_blocked(single_ip) for single_ip in ip_addr]
        ip_addr = ip_addr.lower()

        if not ip_addr_is_valid(ip_addr):
            warn(f"[Warning] {ip_addr} is not a valid IP address to check")
            return False

        return len(BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                          BlockedIP.active).all()) > 0

    def refresh(self, db, timestamp: Union[datetime, None] = None):
        """
        Unblocks from the service those IPs whose block duration has been reached, and blocks those that have exceeded
        the maximum number of failed attempts
        """
        if self.settings.stopped:
            return
        timestamp = timestamp or datetime.now()

        # If the block isn't permanent, unblock IPs that have already exceeded the block duration
        if self.settings.block_duration:
            expired = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.active,
                                             BlockedIP.blocked_at < timestamp - timedelta(
                                                 minutes=float(self.settings.block_duration)))
            for e in expired.all():
                self.unblock(e.ip_addr, db, timestamp)

    def toggle_stopped(self, new_value: bool = None):
        """
        For the changes to be permanent, the persist_settings() method needs to be called afterwards
        """
        new_value = not self.settings.stopped if new_value is None else new_value
        if self.settings.stopped != new_value:
            self.settings.stopped = new_value
            self.flag_as_modified()
        if not new_value:
            self.init_components()

    def get_blocked_ips(self, last_24h: bool = False, historic: bool = False):
        timestamp = datetime.now()
        if historic:  # Return also older IPs
            blocked_ips = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id)
        elif last_24h:
            blocked_ips = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id,
                                                 BlockedIP.blocked_at >= timestamp - timedelta(minutes=60 * 24))
        else:  # Only currently blocked IPs
            blocked_ips = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id,
                                                 BlockedIP.active)
        return [
            {'ip_address': single_ip.ip_addr, 'blocked_at': single_ip.blocked_at, 'active': single_ip.active}
            for single_ip in blocked_ips.order_by(desc(BlockedIP.blocked_at))
        ]

    def get_last_blocked(self):
        result = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id).order_by(
            desc(BlockedIP.blocked_at)).first()
        return None if result is None else result.blocked_at

    def get_info(self):
        while self.modified:
            sleep(.1)
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
            'blocked_24h': len(self.get_blocked_ips(last_24h=True)),
            'last_blocked': datetime_difference(self.get_last_blocked())
        }

    def delete(self, db: SQLAlchemy):
        LoginAttempt.query.filter(LoginAttempt.service_id == self.settings.id).delete()
        BlockedIP.query.filter(BlockedIP.service_id == self.settings.id).delete()
        ServiceSettings.query.filter(ServiceSettings.id == self.settings.id).delete()
        db.session.commit()
        self.settings = None

    @staticmethod
    def is_service_valid(service_name: str, log_path: str = None, web_path: str = None):
        """
        Checks if the desired service is supported
        """
        return service_name in ProtectedService._REGEX_LIST.keys()  # TODO: proper validation


class BackgroundIPS:
    """
    Background process which initiates the watching of log files
    """

    def __init__(self, db: SQLAlchemy):
        self.services = []
        self.admin_pwd = 'EasIPS'
        self.delta_t = 0.5
        self.db = db

    def load_db(self):
        for s in ServiceSettings.query.all():
            self.add_service(s)

    def add_service(self, settings: ServiceSettings):
        service = ProtectedService(settings)
        self.services.append(service)
        try:
            service.flag_as_modified()
        except InvalidSettingsException:
            pass

    def get_service(self, service_id: int) -> ProtectedService:
        for s in self.services:
            if int(s.settings.id) == int(service_id):
                return s
        raise NotFoundException

    def del_service(self, service_id: int):
        s = self.get_service(service_id)
        s.settings.stopped = True
        s.delete(self.db)
        self.services.remove(s)

    def get_services_info(self) -> list:
        return [s.get_info() for s in self.services]

    def set_admin_pwd(self, new_pwd: str):
        self.admin_pwd = new_pwd

    def run(self):
        while True:
            iter_start = time()
            for service in self.services:
                service.iteration(self.db)
            sleep(max(.01, self.delta_t - time() + iter_start))
