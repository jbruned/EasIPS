import subprocess
from abc import ABC, abstractmethod
from typing import Union

from easips.util import modify_ufw_rule, system_call

BLOCKED_HTML = "<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1, shrink-to-fit=no'>" \
               "<title>Forbidden | EasIPS</title><link href='./assets/bootstrap.min.css' rel='stylesheet'>" \
               "<link href='./assets/bootstrap-icons.css' rel='stylesheet'></head><body class='bg-light'>" \
               "<main style='height: 100%'>" \
               "<div class='text-center pb-5' style='width: 100%; position: absolute; top: 50%; -ms-transform: translateY(-50%); transform: translateY(-50%);'>" \
               "<h1 class='d-inline'><i class='bi bi-lock-fill me-2'></i>Oops...</h1><p class='lead'>Too many login attempts!</p>" \
               "<p>You have been temporarily locked out of the system</p></div></main></body></html>"


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

    def __init__(self, port: int, protocol: str = "tcp"):
        # TODO: possibility to allow port ranges
        self.port = port
        assert 0 <= port <= 65535
        self.proto = protocol
        assert subprocess.run(['sudo', 'ufw', 'enable'], capture_output=False).returncode == 0

    def block(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        success = True
        for single_ip in ip_addr:
            success &= modify_ufw_rule(f"ufw insert 1 deny from {single_ip} to any port {self.port} proto {self.proto}", True)
            try:
                system_call(f"iptables -I DOCKER -s {single_ip} -p tcp --dport {self.port} -j DROP")  # in case docker is used (docker avoids ufw)
            except:
                pass
        return success

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        success = True
        for single_ip in ip_addr:
            success &= modify_ufw_rule(f"ufw delete deny from {single_ip} to any port {self.port} proto {self.proto}")
            try:
                system_call(f"iptables -D DOCKER -s {single_ip} -p tcp --dport {self.port} -j DROP")  # in case docker is used (docker avoids ufw)
            except:
                pass
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
        open(self.path, 'w').close()  # Will throw an Exception if path is not valid or there's a lack of permissions

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
                        new_contents += line
                        error_doc_found = True
                f.close()
            except FileNotFoundError:
                new_contents = "Order allow,deny\nAllow from all\n"
            for found, single_ip in zip(ip_found, ip_addr):
                if not found:
                    new_contents += f"Deny from {single_ip}\n"
            if not error_doc_found:
                new_contents += "ErrorDocument 403 \"" + BLOCKED_HTML + "\"\n"
                # todo blocked_permanent
            new_contents += rest_of_file
            f = open(self.path, "w")
            f.write(new_contents)
            f.close()
            return True
        except Exception as e:
            print(e)
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
        self.daemon = service_daemon_name  # TODO: check if the daemon exists
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
