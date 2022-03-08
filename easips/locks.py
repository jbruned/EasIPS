import subprocess as sub
from abc import ABC, abstractmethod
from typing import Union


class ServiceLock(ABC):
    """
    This interface is used to implement adapters to block IPs from each of the required services
    """

    @abstractmethod
    def block(self, ip_addr: Union[str, list]) -> bool:
        """
        This method blocks the specified IP address(es) from the corresponding service.
        It needs to be implemented in each subclass.
        """
        raise NotImplementedError

    @abstractmethod
    def unblock(self, ip_addr: Union[str, list]) -> bool:
        """
        This method blocks the specified IP address(es) from the corresponding service.
        It needs to be implemented in each subclass.
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def web_path_needed() -> bool:
        """
        This static method returns True if the lock needs the root path of the web
        (e.g.: to create a .htaccess file), and False otherwise
        """
        raise NotImplementedError


class SSHLock(ServiceLock):
    """
    This class is capable of (un)blocking IP addresses from a SSH server
    Note: root permissions are required to edit the required firewall settings
    """

    def block(self, ip_addr: Union[str, list]) -> bool:
        # sudo ufw insert 1 deny from IP_ADDRESS to any port 22 proto tcp
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        for single_ip in ip_addr:
            sub.call(['ufw', 'insert', '1', 'deny', 'from', single_ip, 'to', 'any', 'port', '22', 'proto', 'tcp'])
        return True  # TODO Return True if system call is successful, False otherwise

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        # sudo ufw delete deny from IP_ADDRESS to any port 22 proto tcp
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        for single_ip in ip_addr:
            sub.call(['ufw', 'delete', 'deny', 'from', single_ip, 'to', 'any', 'port', '22', 'proto', 'tcp'])
        return True  # TODO Return True if system call is successful, False otherwise

    @staticmethod
    def web_path_needed() -> bool:
        return False


class HTAccessLock(ServiceLock):
    """
    This class is capable of (un)blocking IP addresses from a web service
    This method is based on modifying the .htaccess file on the desired path
    """

    def block(self, ip_addr: Union[str, list]) -> bool:
        # TODO
        return True

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        # TODO
        return True

    @staticmethod
    def web_path_needed() -> bool:
        return True
