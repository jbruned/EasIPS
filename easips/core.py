from datetime import datetime, timedelta
from time import sleep, time
from typing import Union

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

from easips.db import ServiceSettings, LoginAttempt, BlockedIP, StaticRule
from easips.locks import ServiceLock, HTAccessLock, FirewallLock, DaemonLock
from easips.log import debug, log_error, log_warning, log_info
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
        @param settings: model from the database with the service settings
        """
        self.settings = settings
        self.login_tracker = None
        self.lock = None
        self.modified = False

    def _get_lock(self):
        """
        Gets the appropriate ServiceLock based on the service settings
        """
        if self.settings.service == 'easips':
            self.lock = None
        elif self.settings.lock_resource.isnumeric():
            self.lock = FirewallLock(int(self.settings.lock_resource))
        elif '/' in self.settings.lock_resource:
            self.lock = HTAccessLock(self.settings.lock_resource,
                                     f"easips/web/blocked_{'temp' if self.settings.block_duration else 'perm'}.html")
        else:
            self.lock = DaemonLock(self.settings.lock_resource)

    _REGEX_LIST = {
        'joomla': [
            # language=regexp Detect joomla in error log
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}\tINFO\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\tjoomlafailure\t.*Username.*password.*not.*match.*'
        ],
        'wordpress': [
            # language=regexp Detect specific apache log lines
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*POST\s/wp-login\.php.*\s200\s\d+.*'
        ],
        'ssh': [
            # language=regexp Detect in log from rsyslog
            r'^\w{3}\s*\d{1,2}\s\d{2}:\d{2}:\d{2}.*ssh.*repeated\s(\d+)\stimes.*Fail.*password.*\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*',
            # language=regexp Alternative regular expression
            r'^\w{3}\s*\d{1,2}\s\d{2}:\d{2}:\d{2}.*ssh.*Fail.*password.*\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*',
        ],
        'phpmyadmin': [
            # language=regexp Detect in log from rsyslog Detect specific apache log lines
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*POST\s/index\.php.*\s200\s\d+.*'
        ],
        'easips': [
            # language=regexp Detect login attempts in our own log files
            r'\[Warning]\sFailed\slogin\sattempt\sto\sthe\sadmin\spanel\sfrom\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        ]
    }

    def _get_tracker(self):
        """
        Gets the appropriate LoginTracker based on the service settings
        @raise an Exception if something went wrong (file doesn't exist / not enough permissions / invalid port / ...)
        """
        self.login_tracker = LogSniffer(self.settings.log_path, self._REGEX_LIST[self.settings.service])

    def init_components(self):
        """
        Initializes both the LoginTracker and the Lock or raises an InvalidSettingsException
        """
        try:
            self._get_tracker()
            self._get_lock()
        except Exception as e:
            debug(e)
            self.login_tracker = None
            self.lock = None
            if not self.settings.stopped:
                self.toggle_stopped(True)
            log_error(f"Couldn't initialize service '{self.settings.name}', thus it has been stopped")
            raise InvalidSettingsException

    def are_components_initialized(self) -> bool:
        """
        @return: True if the LoginTracker is initialized (Lock may be None in the case of the EasIPS service)
        """
        return self.login_tracker is not None  # and self.lock is not None

    def iteration(self, db: SQLAlchemy):
        """
        Method which should be called constantly from a main loop
        It looks for new failed attempts, (un)locks IP addresses as needed and persists data
        @param db: The database where to persist service settings, login attempts and blocked IPs
        """
        if self.settings is None:
            return
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

    def persist_settings(self, db: SQLAlchemy):
        """
        Add or update the settings of this service to database
        @param db: the database where to persist service settings
        """
        if self.settings.id and ServiceSettings.query.get(self.settings.id):
            pass
        else:
            # Insert if the service doesn't exist
            db.session.add(self.settings)
        db.session.commit()
        self.modified = False

    def log_attempt(self, ip_addr: str, db: SQLAlchemy, timestamp: Union[datetime, None] = None):
        """
        This method logs when an IP has made a login attempt. If it violates the set constraints, it will be blocked.
        @param ip_addr: The IP address that has attempted to log in
        @param db: The database in order to persist login attempts and blocked IPs
        @param timestamp: The moment at which this IP has tried to log in (and thus the moment to be considered when
                          processing it). Defaults to current timestamp.
        """
        timestamp = timestamp or datetime.now()
        if not ip_addr_is_valid(ip_addr):
            log_warning(f"{ip_addr} is not a valid IP address to log")
        elif self.is_blocked(ip_addr):
            log_warning(f"{ip_addr} is supposed to be blocked from '{self.settings.name}' "
                        "but a login attempt has been detected")
        else:
            # Log failed attempt
            db.session.add(LoginAttempt(
                service_id=self.settings.id,
                ip_addr=ip_addr,
                timestamp=timestamp
            ))
            db.session.commit()
        # Block the IP if needed
        if self.has_exceeded_attempts(ip_addr, timestamp):
            self.block(ip_addr, db, timestamp)

    def has_exceeded_attempts(self, ip_addr: str, timestamp: Union[datetime, None] = None) -> bool:
        """
        Checks if a certain IP needs to be blocked by looking at its recent login attempts
        @param ip_addr: The IP address that needs to be checked
        @param timestamp: The moment at which we want to know if this IP needs to be blocked (defaults to now)
        @return: True if the IP has exceeded the maximum number of attempts within the specified time span
        """
        timestamp = timestamp or datetime.now()
        return len(LoginAttempt.query.filter(
            LoginAttempt.service_id == self.settings.id,
            LoginAttempt.ip_addr == ip_addr,
            LoginAttempt.timestamp >= timestamp - timedelta(minutes=self.settings.time_threshold)
        ).all()) >= self.settings.max_attempts

    def block(self, ip_addr: Union[str, list], db: SQLAlchemy, timestamp: Union[datetime, None] = None):
        """
        Block a certain IP address from the service (if successful, it stores the blocked IP to the database as well)
        @param ip_addr: The IP address that needs to be blocked
        @param db: The database in order to persist the blocked IP if block is successful
        @param timestamp: The moment at which this IP was blocked (defaults to current timestamp)
        """
        timestamp = timestamp or datetime.now()
        if isinstance(ip_addr, list):
            for single_ip in ip_addr:
                self.block(single_ip, db, timestamp)
        else:
            ip_addr = ip_addr.lower()
            if not ip_addr_is_valid(ip_addr):
                log_warning(f"{ip_addr} is not a valid IP address to block")
                return
            # First check whitelist and blacklist
            static = self.is_blocked_static(ip_addr)
            if static is not None:
                log_warning(f"Tried to block {ip_addr}, which is in the {'blacklist' if static else 'whitelist'}")
            elif self.is_blocked(ip_addr):
                # If it's already blocked (this can happen when many requests from the same IP arrive very quickly)
                obj = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                             BlockedIP.active).first()
                obj.blocked_at = timestamp
                db.session.commit()
                log_info(f"{ip_addr} was already blocked from '{self.settings.name}', time is now updated")
            elif self.settings.service == 'easips' or self.lock.block(ip_addr):
                # Persist blocked IP to the database
                db.session.add(BlockedIP(
                    service_id=self.settings.id,
                    ip_addr=ip_addr,
                    blocked_at=timestamp,
                    active=True
                ))
                db.session.commit()
                log_info(f"{ip_addr} has been successfully blocked from service '{self.settings.name}'")
            else:
                # If the Lock object fails to unblock the specified address
                log_error(f"{ip_addr} couldn't be blocked from service '{self.settings.name}'")

    def unblock(self, ip_addr: Union[str, list], db: SQLAlchemy, timestamp: Union[datetime, None] = None):
        """
        Unblock a certain IP address from the service (if successful, it disables the block from the database as well)
        @param ip_addr: The IP address that needs to be unblocked
        @param db: The database in order to persist the unblocked IP if successful
        @param timestamp: The moment at which this IP was unblocked (defaults to current timestamp)
        """
        timestamp = timestamp or datetime.now()
        if isinstance(ip_addr, list):
            for single_ip in ip_addr:
                self.unblock(single_ip, db, timestamp)
        else:
            ip_addr = ip_addr.lower()
            if not ip_addr_is_valid(ip_addr):
                log_warning(f"{ip_addr} is not a valid IP address to unblock")
                return
            # First check whitelist and blacklist
            static = self.is_blocked_static(ip_addr)
            if static is not None:
                log_warning(f"Tried to unblock {ip_addr}, which is in {self.settings.name}'s "
                            f"{'blacklist' if static else 'whitelist'}")
            elif not self.is_blocked(ip_addr):
                log_info(f"Attempted to unblock not blocked address {ip_addr} from service '{self.settings.name}'")
            elif self.settings.service == 'easips' or self.lock.unblock(ip_addr):
                # Persist IP unlock to the database
                query = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                               BlockedIP.active)
                for obj in query.all():
                    obj.active = False
                db.session.commit()
                log_info(f"{ip_addr} has been successfully unblocked from service '{self.settings.name}'")
            else:
                # If the Lock object fails to unblock the specified address
                log_error(f"{ip_addr} couldn't be unblocked from service '{self.settings.name}'")

    def create_static_rule(self, ip_addr: str, set_blocked: bool, db: SQLAlchemy):
        """
        Adds a rule to the whitelist or blacklist
        @param ip_addr: the IP address to whitelist/blacklist
        @param set_blocked: if True, the IP is blacklisted; otherwise, it's whitelisted
        @param db: the database where to persist the new rule
        """
        # First (un)block the IP address if necessary
        is_blocked = self.is_blocked(ip_addr)
        try:
            if self.settings.service != 'easips':
                if is_blocked and not set_blocked:
                    self.lock.unblock(ip_addr)
                elif not is_blocked and set_blocked:
                    self.lock.unblock(ip_addr)
            query = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                           BlockedIP.active)
            for obj in query.all():
                obj.active = False
        except Exception as e:
            debug(e)
        # Look for already existing rules
        if self.is_blocked_static(ip_addr) is not None:
            self.remove_static_rule(ip_addr, db)
        # Create and persist the new rule
        db.session.add(StaticRule(
            service_id=self.settings.id,
            ip_addr=ip_addr,
            added_at=datetime.now(),
            blocked=set_blocked
        ))
        db.session.commit()
        log_info(f"Added {ip_addr} to {self.settings.name}'s {'blacklist' if set_blocked else 'whitelist'}")

    def remove_static_rule(self, ip_addr: str, db: SQLAlchemy):
        """
        Remove a rule from the whitelist/blacklist
        @param ip_addr: the IP address to remove from the whitelist/blacklist
        @param db: the database where the rules are stored
        """
        StaticRule.query.filter(StaticRule.service_id == self.settings.id, StaticRule.ip_addr == ip_addr).delete()
        if db is not None:
            db.session.commit()

    def is_blocked(self, ip_addr: Union[str, list]) -> Union[bool, list]:
        """
        Determines if the specified IP address(es) is/are blocked from the specified service.
        @param ip_addr: IP address (string) or list of IP addresses (list) to check
        @return: boolean value when checking a single IP, list of booleans otherwise
        """
        if isinstance(ip_addr, list):
            return [self.is_blocked(single_ip) for single_ip in ip_addr]
        ip_addr = ip_addr.lower()

        if not ip_addr_is_valid(ip_addr):
            log_warning(f"{ip_addr} is not a valid IP address to check")
            return False

        static = self.is_blocked_static(ip_addr)
        if static is not None:
            return static

        return len(BlockedIP.query.filter(BlockedIP.service_id == self.settings.id, BlockedIP.ip_addr == ip_addr,
                                          BlockedIP.active).all()) > 0

    def is_blocked_static(self, ip_addr: str) -> bool:
        """
        Determines if the specified IP address is blocked from the service according to the whitelist/blacklist
        @param ip_addr: IP address (string) or list of IP addresses (list) to check
        @return: boolean value when checking a single IP, list of booleans otherwise
        """
        static = StaticRule.query.filter(StaticRule.service_id == self.settings.id, StaticRule.ip_addr == ip_addr)
        return static.first().blocked if len(static.all()) > 0 else None

    def refresh(self, db: SQLAlchemy, timestamp: Union[datetime, None] = None):
        """
        Unblocks from the service those IPs whose block duration has been reached
        @param db: database where blocked IPs are stored
        @param timestamp: the moment where the refresh was initiated (defaults to the current timestamp)
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
        Changes the running state (running/stopped) of the current service
        For the changes to be permanent, the persist_settings() method needs to be called afterwards
        @param new_value: if provided, the service will be stopped (True) or resumed (False) instead of toggling state
        """
        new_value = not self.settings.stopped if new_value is None else new_value
        if self.settings.stopped != new_value:
            self.settings.stopped = new_value
            self.flag_as_modified()
        if not new_value:
            self.init_components()

    def get_static_rules(self, only_blocked: bool = False) -> list:
        """
        Returns whitelisted/blacklisted IPs
        @param only_blocked: if True, only blacklisted  (default is False)
        @return: list of blacklisted IP addresses (if @param only_blocked) or list of dictionaries containing information
                 about whitelisted/blacklisted IPs (if not @param only_blocked)
        """
        results = StaticRule.query.filter(StaticRule.service_id == self.settings.id).all()
        return [result.ip_addr for result in results if result.blocked] if only_blocked else [{
            'ip_address': result.ip_addr,
            'blocked': result.blocked,
            'added_at': str(result.added_at)
        } for result in results]

    def get_blocked_ips(self, last_24h: bool = False, historic: bool = False) -> list:
        """
        Returns information about the blocked IP addresses
        @param last_24h: returns blocked IPs during the last 24h
        @param historic: returns history of all blocked IP addresses
        @return: list of dictionaries containing information about blocked IPs
        """
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
        ] + [
            {'ip_address': ip_addr, 'blocked_at': 'Blacklisted', 'active': True}
            for ip_addr in self.get_static_rules(True)
        ]

    def get_last_blocked(self) -> datetime:
        """
        Get the timestamp at which the last IP address was blocked
        @return: datatime object specifying when the last IP address was blocked
        """
        result = BlockedIP.query.filter(BlockedIP.service_id == self.settings.id).order_by(
            desc(BlockedIP.blocked_at)).first()
        return None if result is None else result.blocked_at

    def get_info(self):
        """
        Gives information about the service, its settings and its current status
        Intended to be used to pass information to the GUI in JSON format (JSON encoding is NOT performed here)
        @return: dict with information about the service
        """
        # If it is flagged as modified, wait for the data to be persisted
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
            'lock_resource': self.settings.lock_resource,
            'stopped': self.settings.stopped,
            'blocked_now': len(self.get_blocked_ips()),
            'blocked_24h': len(self.get_blocked_ips(last_24h=True)),
            'last_blocked': datetime_difference(self.get_last_blocked())
        }

    def delete(self, db: SQLAlchemy):
        """
        Remove the current service and all of its dependent objects (login attempts and blocked IPs) from the database
        @param db: database where the service is stored
        """
        LoginAttempt.query.filter(LoginAttempt.service_id == self.settings.id).delete()
        BlockedIP.query.filter(BlockedIP.service_id == self.settings.id).delete()
        ServiceSettings.query.filter(ServiceSettings.id == self.settings.id).delete()
        db.session.commit()
        self.settings = None

    @staticmethod
    def is_service_name_valid(service_name: str) -> bool:
        """
        Checks if the desired service is supported
        @return: boolean specifying if the service name is valid
        """
        return service_name in ProtectedService._REGEX_LIST.keys()


class BackgroundIPS:
    """
    Background process of EasIPS which instantiates and constantly polls all the protected services
    """

    def __init__(self, db: SQLAlchemy, delta_t: float = .5):
        """
        BackgroundIPS's constructor
        @param db: database where data is persisted
        @param delta_t: how much time to wait between one poll and the next one
                        (i.e.: if delta_t is 0.5, every second 2 iterations are executed)
        """
        self.services = []
        self.delta_t = delta_t
        self.db = db

    def load_db(self):
        """
        Perform initial data loading from the database (loads and runs all existing protected services)
        """
        try:
            for s in ServiceSettings.query.all():
                self.add_service(s)
            if len(self.services) == 0:
                self.add_service(ServiceSettings(
                    name="EasIPS Admin Panel",
                    service="easips",
                    time_threshold=5,
                    max_attempts=5,
                    block_duration=5,
                    log_path="easips.log",
                    lock_resource=None,
                    stopped=False
                ))
        except InvalidSettingsException:
            pass

    def add_service(self, settings: ServiceSettings):
        """
        Add a new service to the background thread
        @param settings: settings object with information from the database
        """
        service = ProtectedService(settings)
        self.services.append(service)
        service.flag_as_modified()

    def get_service(self, service_id: int) -> ProtectedService:
        """
        Get the ProtectedService object for the specified service id
        @param service_id: id of the desired service
        @return: requested ProtectedService object
        @raise: NotFoundException if the service_id doesn't exist
        """
        for s in self.services:
            if int(s.settings.id) == int(service_id):
                return s
        raise NotFoundException

    def get_easips_service(self) -> ProtectedService:
        """
        Get the ProtectedService for our own web GUI login
        @return: EasIPS's ProtectedService object
        @raise: NotFoundException if the service_id doesn't exist (actually this should never happen because the
                service is created by default on first application start and can't be deleted by the user)
        """
        for s in self.services:
            if s.settings.service == 'easips':
                return s
        raise NotFoundException

    def del_service(self, service_id: int):
        """
        Remove the specified ProtectedService from the background thread and from the database
        @param service_id: id of the service
        @raise: NotFoundException if the service_id doesn't exist
        """
        s = self.get_service(service_id)
        s.settings.stopped = True
        s.delete(self.db)
        self.services.remove(s)

    def get_services_info(self) -> list:
        """
        Gives information about every service, its settings and its current status
        Intended to be used to pass information to the GUI in JSON format (JSON encoding is NOT performed here)
        @return: list of dictionaries with information about all the existing services
        """
        return [s.get_info() for s in self.services]

    def run(self):
        """
        This is the main loop of the IPS, it's run constantly in its own thread
        """
        while True:
            iter_start = time()
            for service in self.services:
                service.iteration(self.db)
            sleep(max(.01, self.delta_t - time() + iter_start))
