import subprocess as sub
from flask_sqlalchemy import SQLAlchemy
from abc import ABC, abstractmethod
from typing import Union
from warnings import warn
from ipaddress import ip_address
from time import time
from sys import stderr
import datetime
import easips.gui as app

class BaseBlock (ABC):
	"""
	This interface is used to implement adapters to each of the required services.
	"""

	settings: app.Settings
	db: SQLAlchemy

	def __init__(self, settings, db):
		"""
		BasBlock's constructor
		:param settings: app.Settings -> Specify the set variables for the blocking process, such as the number of attempts, block duration and time span
		:param db: SQLAlchemy -> The database connection. This is used to store and read the login attempts and blocked IPs
		"""
		self.settings = settings
		self.db = db


	def log_ip(self, ip: str, moment: Union[datetime.datetime, None] = None):
		"""
		This method logs when an IP has made a login attempt. If this attempt violates the set constraints, it will be blocked.
		This method also takes care of removing the blocked addresses in due time.
		:param ip: str -> The IP address that has attempted to log in
		:param moment: datetime.datetime | None -> The moment at which this IP has tried to log in, and thus the moment to be considered in processing it. Defaults to current time
		"""
		if moment is None:
			moment = datetime.datetime.now()

		if not BaseBlock.ip_addr_is_valid(ip):
			warn(f"[Warning] {ip} is not a valid IP address to log")
		else:
			self.db.session.add(app.IPLoginTry(
				ip=ip,
				moment=moment
			))
			self.db.session.commit()  # enter new try

		self.refresh(moment)
		self.block_if_needed(ip, moment)


	@staticmethod
	def ip_addr_is_valid(ip_addr: str) -> bool:
		"""
		Returns True if the input IP address is a valid IPv4/IPv6 address
		"""
		try:
			ip_address(ip_addr)
			return True
		except ValueError:
			return False

	def block(self, ip_addr: Union[str, list], moment: Union[datetime.datetime, None] = None):
		"""
		This method blocks the specified IP address(es) from the corresponding service.
		The provided time will be regarded as the moment at which it is blocked. This defaults to the current time.
		"""
		if moment is None:
			moment = datetime.datetime.now()

		if isinstance(ip_addr, list):
			for single_ip in ip_addr:
				self.block(single_ip, moment)
		else:
			ip_addr = ip_addr.lower()
			if not BaseBlock.ip_addr_is_valid(ip_addr):
				warn(f"[Warning] {ip_addr} is not a valid IP address to block")
			elif self.is_blocked(ip_addr, moment):
				print(f"[Info] {ip_addr} was already blocked from service '{self.get_service_name()}', time is now updated")
			elif self._block_from_service(ip_addr):
				print(f"[Info] {ip_addr} has been successfully blocked from service '{self.get_service_name()}'")
			else:
				print(f"[Error] {ip_addr} couldn't be blocked from service '{self.get_service_name()}'", file=stderr)

	def unblock(self, ip_addr: Union[str, list]):
		"""
		This method unblocks the specified IP address from the corresponding service
		"""
		if isinstance(ip_addr, list):
			for single_ip in ip_addr:
				self.unblock(single_ip)
		else:
			ip_addr = ip_addr.lower()
			if not BaseBlock.ip_addr_is_valid(ip_addr):
				warn(f"[Warning] {ip_addr} is not a valid IP address to unblock")
			elif not self.is_blocked(ip_addr):
				print(f"[Info] Attempted to unblock not blocked address {ip_addr} from service '{self.get_service_name()}'")
			elif self._unblock_from_service(ip_addr):
				print(f"[Info] {ip_addr} has been successfully unblocked from service '{self.get_service_name()}'")
			else:
				print(f"[Error] {ip_addr} couldn't be unblocked from service '{self.get_service_name()}'", file=stderr)

	def is_blocked(self, ip_addr: Union[str, list], moment: Union[datetime.datetime, None] = None) -> Union [bool, list]:
		"""
		Determines if the IP address(es) are blocked from the specified service.
		If :param moment: is provided, it will also update the time of said block to the provided moment.
		"""
		if not moment:
			moment = datetime.datetime.now()

		if isinstance(ip_addr, list):
			return [self.is_blocked(single_ip, moment) for single_ip in ip_addr]
		ip_addr = ip_addr.lower()
		if not BaseBlock.ip_addr_is_valid(ip_addr):
			warn(f"[Warning] {ip_addr} is not a valid IP address to check")
			return False

		exists = False
		for bi in app.BlockedIP.query.filter(app.BlockedIP.ip == ip_addr):
			exists = True
			if moment:
				bi.blocked_at = moment
				self.db.session.add(bi)
			else:
				break

		if moment:		
			self.db.session.commit()
		return exists


	def refresh(self, moment: Union[datetime.datetime, None] = None):
		"""
		Unblocks from the service those IPs whose block duration has been reached, and blocks those that have exceeded their tries
		"""
		if moment is None:
			moment = datetime.datetime.now()

		app.IPLoginTry.query.filter(
			app.IPLoginTry.moment < moment - datetime.timedelta(minutes=self.settings.time)
		).delete()  # remove old tries

		if self.settings.block_len:
			# the blocks aren't indefinitely? Then it might be time for some unblocking
			expire = app.BlockedIP.query.filter(app.BlockedIP.blocked_at < moment - datetime.timedelta(minutes=self.settings.block_len))
			for e in expire:
				self.unblock(e.ip)
			expire.delete()

	def block_if_needed(self, ip: str, moment: Union[datetime.datetime, None] = None):
		"""
		Checks if a certain IP needs to be blocked by looking at its recent login attempts. This also deletes the old ones.
		"""
		if moment is None:
			moment = datetime.datetime.now()

		if len(app.IPLoginTry.query.filter(
					app.IPLoginTry.ip == ip and
					app.IPLoginTry.moment >= moment - datetime.timedelta(minutes=self.settings.time)
				).all()) >= self.settings.tries:
			if not self.is_blocked(ip, moment):
				self.db.session.add(app.BlockedIP(
					ip=ip,
					blocked_at=moment
				))
				self.db.session.commit()
				self.block(ip, moment)

	def clear(self):
		"""
		Unblocks every IP from the service
		"""
		self.unblock(list(self.blocked.keys()))

	@abstractmethod
	def get_service_name(self) -> str:
		"""
		Returns the name of the service being handled by a specific block.
		This method should be implemented in each subclass extending from the BaseBlock class
		:return Name of the service
		"""
		raise NotImplementedError

	@abstractmethod
	def _block_from_service(self, ip_addr: str) -> bool:
		"""
		Blocks the IP address from the desired service.
		This method:
			- Must be implemented in each subclass implementing the BaseBlock class
			- Shouldn't be called directly; instead, block_ip() should be called
		:return True if block was successful, False otherwise
		"""
		raise NotImplementedError

	@abstractmethod
	def _unblock_from_service(self, ip_addr: str) -> bool:
		"""
		Unblocks the IP address from the desired service.
		This method:
			- Must be implemented in each subclass implementing the BaseBlock class
			- Shouldn't be called directly; instead, unblock_ip() should be called
		:return True if unblock was successful, False otherwise
		"""
		raise NotImplementedError


class SSHBlock (BaseBlock):
	"""
	This class is capable of (un)blocking IP addresses for SSH connections.
	Note: root permissions are required to edit the required firewall settings
	"""

	def get_service_name(self) -> str:
		return "SSH"

	def _block_from_service(self, ip_addr: str) -> bool:
		# sudo ufw insert 1 deny from IP_ADDRESS to any port 22 proto tcp
		sub.call(['ufw', 'insert', '1', 'deny', 'from', ip_addr, 'to', 'any', 'port', '22', 'proto', 'tcp'])
		return True # TODO Return True if system call is successful, False otherwise

	def _unblock_from_service(self, ip_addr: str) -> bool:
		# sudo ufw delete deny from IP_ADDRESS to any port 22 proto tcp
		sub.call(['ufw', 'delete', 'deny', 'from', ip_addr, 'to', 'any', 'port', '22', 'proto', 'tcp'])
		return True # TODO Return True if system call is successful, False otherwise
