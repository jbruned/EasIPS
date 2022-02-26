import subprocess as sub
from abc import ABC, abstractmethod
from typing import Union
from warnings import warn
from ipaddress import ip_address
from time import time
from sys import stderr

class BaseBlock (ABC):
	"""
	This interface is used to implement adapters to each of the required services.
	"""

	blocked: dict
	block_duration: Union[int, None]
	persist_to_file: Union[bool, str]

	def __init__(self, block_duration: int = None, persist_to_file: Union[bool,  str] = True):
		"""
		BasBlock's constructor
		:param block_duration: int -> Specify the block duration in minutes (integer > 0 or None for permanent block)
					 			      Default value: None
		:param persist_to_file: bool | str -> False prevents the list of IP addresses from being saved to a file
										      Otherwise, the file name should be specified (or True for default name)
		"""
		self.blocked = {}
		if block_duration is None or block_duration > 0:
			self.block_duration = block_duration
		else:
			self.block_duration = None
			warn(f"[Warning] Invalid block duration ({block_duration}), defaulting to permanent block")
		self.persist_to_file = persist_to_file


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

	def block(self, ip_addr: Union[str, list]):
		"""
		This method blocks the specified IP address(es) from the corresponding service
		"""
		if isinstance(ip_addr, list):
			for single_ip in ip_addr:
				self.block(single_ip)
		else:
			ip_addr = ip_addr.lower()
			if not BaseBlock.ip_addr_is_valid(ip_addr):
				warn(f"[Warning] {ip_addr} is not a valid IP address to block")
			elif self.is_blocked(ip_addr):
				print(f"[Info] {ip_addr} was already blocked from service '{self.get_service_name()}'")
			elif self._block_from_service(ip_addr):
				self.blocked[ip_addr] = time()
				self.store_blocked()
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
				del self.blocked[ip_addr]
				self.store_blocked()
				print(f"[Info] {ip_addr} has been successfully unblocked from service '{self.get_service_name()}'")
			else:
				print(f"[Error] {ip_addr} couldn't be unblocked from service '{self.get_service_name()}'", file=stderr)

	def is_blocked(self, ip_addr: Union[str, list]) -> Union [bool, list]:
		"""
		Determines if the IP address(es) are blocked from the specified service
		"""
		if isinstance(ip_addr, list):
			return [self.is_blocked(single_ip) for single_ip in ip_addr]
		ip_addr = ip_addr.lower()
		if not BaseBlock.ip_addr_is_valid(ip_addr):
			warn(f"[Warning] {ip_addr} is not a valid IP address to check")
			return False
		return ip_addr not in self.blocked.keys() and \
			   (self.block_duration is None or time() - self.blocked[ip_addr] > self.block_duration)

	def store_blocked(self, file_name: str = None):
		"""
		Saves the list of blocked IP addresses to a file
		"""
		if not self.persist_to_file:
			warn("[Warning] List of blocked IPs wasn't saved because persist_to_file = False was passed to constructor")
			return
		file_name = file_name or f"blocked_{self.get_service_name().lower()}"
		try:
			f = open(file_name, "w")
			f.write('\n'.join(self.blocked.keys()))
			f.close()
			print(f"[Info] Saved {len(self.blocked)} blocked IPs from '{self.get_service_name}' to file '{file_name}'")
		except IOError:
			print(f"[Error] Couldn't write blocked IP addresses to file '{file_name}', check permissions", file=stderr)

	def load_blocked(self, file_name: str = None):
		"""
		Loads the list of blocked IP addresses from a file
		"""
		file_name = file_name or f"blocked_{self.get_service_name().lower()}"
		try:
			f = open(file_name, "r")
			self.blocked = {single_ip: time() for single_ip in f.read().split('\n')}
			f.close()
			print(f"[Info] Loaded {len(self.blocked)} blocked IPs from '{self.get_service_name}' from '{file_name}'")
		except FileNotFoundError:
			print(f"[Error] Couldn't load blocked IP addresses from file '{file_name}' because it doesn't exist",
				  file=stderr)
		except IOError:
			print(f"[Error] Couldn't load blocked IP addresses from file '{file_name}', check permissions", file=stderr)

	def refresh(self):
		"""
		Unblocks from the service those IPs whose block duration has been reached
		"""
		if self.block_duration is None:
			return
		for single_ip, block_start in self.blocked.items():
			if time() - block_start > self.block_duration:
				self.unblock(single_ip)

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
