import subprocess as sub
from abc import ABC, abstractmethod
from typing import Union
from easips.util import system_call
from shutil import copyfile


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


class FirewallLock(ServiceLock):
    """
    This class is capable of (un)blocking IP addresses portwise
    Note: root permissions are required to edit the required firewall settings
    """

    def __init__(self, port: Union[int, str], protocol: str = "tcp"):
        self.port = port
        self.proto = protocol

    def block(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        success = True
        for single_ip in ip_addr:
            success &= system_call(f"ufw insert 1 deny from {single_ip} to any port {self.port} proto {self.proto}")
        return success

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        success = True
        for single_ip in ip_addr:
            success &= system_call(f"ufw delete deny from {single_ip} to any port {self.port} proto {self.proto}")
        return success


class HTAccessLock(ServiceLock):
    """
    This class is capable of (un)blocking IP addresses from a web service
    This method is based on modifying the .htaccess file on the desired path
    """

    def __init__(self, web_path: str):
        if web_path[-1] != '/' and web_path[-1] != '\\':
            web_path += '/'
        self.path = web_path + '.htaccess'

    def block(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        ip_addr = [x.strip().lower() for x in ip_addr]
        ip_found = [False for _ in ip_addr]
        error_doc_found = False
        try:
            rest_of_file = ""
            try:
                f = open(self.path, "r")
                new_contents = ""
                order_found = False
                allow_found = False
                for line in f:
                    if line.strip() == "":
                        continue
                    elif not order_found:
                        if 'order ' in line.lower():
                            order_found = True
                            new_contents += "Order allow,deny\n"
                    elif not allow_found:
                        new_contents += "Allow from all\n"
                        allow_found = True
                    else:
                        if "Deny from " in line:
                            for i in range(len(ip_addr)):
                                if ip_addr[i] in line:
                                    ip_found[i] = True
                            new_contents += line
                        else:
                            rest_of_file += line
                    if "ErrorDocument 403 " in line:
                        new_contents += "ErrorDocument 403 blocked.html\n"
                        error_doc_found = True
                f.close()
            except FileNotFoundError:
                new_contents = "Order allow,deny\nAllow from all\n"
            for found, single_ip in zip(ip_found, ip_addr):
                if not found:
                    new_contents += f"Deny from {single_ip}\n"
            if not error_doc_found:
                new_contents += "ErrorDocument 403 blocked.html\n"
            copyfile(self.path.replace('.htaccess', 'blocked.html'), "web/blocked.html")
            new_contents += rest_of_file
            f = open(self.path, "w")
            f.write(new_contents)
            f.close()
            return True
        except:
            return False

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        ip_addr = [x.strip().lower() for x in ip_addr]
        try:
            f = open(self.path, "r")
            new_contents = ""
            for line in f:
                for single_ip in ip_addr:
                    if single_ip not in line or "Deny from " not in line:
                        new_contents += line
            f.close()
            f = open(self.path, "w")
            f.write(new_contents)
            f.close()
            return True
        except FileNotFoundError:
            return True
        except:
            return False


class EtcHostsLock(ServiceLock):
    """
    This class is capable of (un)blocking IP addresses from any daemon
    This method is based on modifying the /etc/hosts.deny file (which needs root access)
    """

    def __init__(self, service_daemon_name: str, etc_hosts_deny_path: str = "/etc/hosts.deny"):
        self.daemon = service_daemon_name
        self.path = etc_hosts_deny_path

    def block(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        try:
            new_contents = ""
            written = False
            try:
                f = open(self.path, "r")
                for line in f:
                    if self.daemon + ' :' in line or self.daemon + ':' in line:
                        written = True
                        ips = [x.strip().lower() for x in line.split(':', 2)[-1].split(',')]
                        for single_ip in ip_addr:
                            single_ip = single_ip.strip().lower()
                            if single_ip not in ips:
                                line += f", {single_ip}"
                    new_contents += line
                f.close()
            except FileNotFoundError:
                pass
            if not written:
                new_contents += self.daemon + ' : ' + ', '.join([x.strip().lower() for x in ip_addr])
            f = open(self.path, "w")
            f.write(new_contents)
            f.close()
            return True
        except:
            return False

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        try:
            f = open(self.path, "r")
            new_contents = ""
            for line in f:
                if self.daemon + ' :' in line or self.daemon + ':' in line:
                    ips = [x.strip().lower() for x in line.split(':', 2)[-1].split(',')]
                    for single_ip in ip_addr:
                        single_ip = single_ip.strip().lower()
                        if single_ip in ips:
                            ips.remove(single_ip)
                    if len(ips) < 1:
                        continue
                    line = self.daemon + ' : ' + ', '.join(ips)
                new_contents += line
            f.close()
            f = open(self.path, "w")
            f.write(new_contents)
            f.close()
            return True
        except FileNotFoundError:
            return True
        except:
            return False
