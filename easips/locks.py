import subprocess
from abc import ABC, abstractmethod
from typing import Union

from easips.log import debug
from easips.util import modify_ufw_rule, system_call


class ServiceLock(ABC):
    """
    This interface is used to implement locks to block IPs from each of the required services
    """

    @abstractmethod
    def block(self, ip_addr: Union[str, list]) -> bool:
        """
        This method blocks the specified IP address(es) from the corresponding service.
        It needs to be implemented in each subclass.
        @param ip_addr: IP address(es) to block
        @return: True if (all of) the block(s) were successful
        """
        raise NotImplementedError

    @abstractmethod
    def unblock(self, ip_addr: Union[str, list]) -> bool:
        """
        This method unblocks the specified IP address(es) from the corresponding service.
        It needs to be implemented in each subclass.
        @param ip_addr: IP address(es) to unblock
        @return: True if (all of) the unblock(s) were successful
        """
        raise NotImplementedError


class FirewallLock(ServiceLock):
    """
    This class is capable of port-wise (un)blocking IP addresses using Linux's built-in firewall
    @note Root permissions are required to edit the required firewall settings
    """

    def __init__(self, port: int, protocol: str = "tcp"):
        """
        FirewallLock's constructor
        @param port: number of port to block
        @param protocol: protocol (tcp/udp)
        @raise: Exception if settings are invalid
        """
        # TODO: possibility to allow port ranges
        self.port = port
        assert 0 <= port <= 65535
        self.proto = protocol
        assert system_call('sudo ufw enable')

    def block(self, ip_addr: Union[str, list]) -> bool:
        """
        Block specified IP address(es) from the port
        @param ip_addr: IP address(es) to block
        @return: True if all blocks succeeded
        """
        return self.manage_ufw_rules(ip_addr, True)

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        """
        Unblock specified IP address(es) from the port
        @param ip_addr: IP address(es) to unblock
        @return: True if all unblocks succeeded
        """
        return self.manage_ufw_rules(ip_addr, False)

    def manage_ufw_rules(self, ip_addr: Union[str, list], block: bool) -> bool:
        """
        Common logic for blocking and unblocking
        @param ip_addr: IP address(es) to (un)block
        @param block: if True, rules are added; otherwise, deleted
        @return: True if all (un)blocks succeeded
        """
        if not isinstance(ip_addr, list):
            ip_addr = [ip_addr]
        success = True
        for single_ip in ip_addr:
            curr_success = modify_ufw_rule(f"ufw {'insert 1' if block else 'delete'} deny from {single_ip} "
                                           f"to any port {self.port} proto {self.proto}")
            try:
                # In case docker is used (docker avoids ufw)
                curr_success |= system_call(f"iptables -{'I' if block else 'D'} DOCKER "
                                            f"-s {single_ip} -p tcp --dport {self.port} -j DROP")
            except Exception as e:
                debug(e)
            success &= curr_success
        return success


class HTAccessLock(ServiceLock):
    """
    This class is capable of path-wise (un)blocking IP addresses from a web service
    This method is based on modifying the .htaccess file on the desired path, which should be write-accessible
    @note The webserver must be Apache-based for .htaccess to work
    """

    def __init__(self, web_path: str, blocked_html_file: str):
        """
        HTAccessLock's constructor
        @param web_path: absolute local path to the folder to be blocked
        @param blocked_html_file: path to the HTML file to show when a blocked user tries to load the website
        @raise: Exception if settings are invalid
        """
        if web_path[-1] != '/' and web_path[-1] != '\\':
            web_path += '/'
        self.path = web_path + '.htaccess'
        f = open(blocked_html_file, "r")
        self.blocked_html = f.read().replace('\n', '').replace('\r', '').replace('"', '\'')
        f.close()
        open(self.path, 'w').close()  # Will throw an Exception if path is not valid or there's a lack of permissions

    def block(self, ip_addr: Union[str, list]) -> bool:
        """
        Block specified IP address(es) from the path
        @param ip_addr: IP address(es) to block
        @return: True if all blocks succeeded
        """
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
                new_contents += 'ErrorDocument 403 "' + self.blocked_html + '"\n'
            new_contents += rest_of_file
            f = open(self.path, "w")
            f.write(new_contents)
            f.close()
            return True
        except Exception as e:
            debug(e)
            return False

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        """
        Unblock specified IP address(es) from the path
        @param ip_addr: IP address(es) to unblock
        @return: True if all unblocks succeeded
        """
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
        except Exception as e:
            debug(e)
            return False


class DaemonLock(ServiceLock):
    """
    This class is capable of (un)blocking IP addresses given the daemon name
    @note This method is based on modifying the /etc/hosts.deny file (which needs Linux arch and root access)
    """

    def __init__(self, service_daemon_name: str, etc_hosts_deny_path: str = "/etc/hosts.deny"):
        """
        DaemonLock's constructor
        @param service_daemon_name: daemon name (e.g.: sshd)
        @param etc_hosts_deny_path: absolute local path to the file (obviously defaults to /etc/hosts.deny)
        @raise: Exception if settings are invalid
        """
        self.daemon = service_daemon_name  # TODO: check if the daemon exists
        self.path = etc_hosts_deny_path

    def block(self, ip_addr: Union[str, list]) -> bool:
        """
        Block specified IP address(es) from the daemon
        @param ip_addr: IP address(es) to block
        @return: True if all blocks succeeded
        """
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
        except Exception as e:
            debug(e)
            return False

    def unblock(self, ip_addr: Union[str, list]) -> bool:
        """
        Unblock specified IP address(es) from the daemon
        @param ip_addr: IP address(es) to unblock
        @return: True if all unblocks succeeded
        """
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
        except Exception as e:
            debug(e)
            return False
