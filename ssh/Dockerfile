FROM ubuntu:20.04
RUN apt-get update && apt-get install -y openssh-server rsyslog && useradd --create-home --base-dir /home newuser && echo "newuser:newuser" | chpasswd
ENTRYPOINT service ssh start; service rsyslog start; touch /var/log/auth.log; chown syslog:adm /var/log/auth.log; while true ; do sleep 100; done;
