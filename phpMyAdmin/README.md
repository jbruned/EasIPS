# PHPMyAdmin Docker Container
PHPMyAdmin docker-compose.yml template is inspired by: https://tecadmin.net/docker-compose-for-mysql-with-phpmyadmin/

# General Information

Please note that the container may not fully work on on Windows. Because of the nature of docker containers, the /var/www/html folder is copied to /tmp on creation of the container. After creating the container, the folder is moved back making them enter our volume space. Sadly, this process causes some problems on Windows.

## Commands of setting up the containers
Setup PHPMyAdmin
```
sudo docker compose up -d
```

Shutdown PHPMyAdmin container and mysql container
```
sudo docker compose down
```

## Installation
Website to access PHPMyAdmin webserver:
><localhost:8082>

Fill in the following information:
Username: 
> root

Password:
> root

## Volumes

The volume of /var of the PHPMyAdmin container is now found in 
>./webserver/var

The volume of for the MySQL container can be found in 
>./database

<br/>

## Logs
Apache 2 Logs can be found at 
>[./webserver/var/log/apache2/access.log](./webserver/var/log/apache2/access.log)

The .htaccess can be found in 
>[./webserver/var/www/html/.htaccess](./webserver/var/www/html/.htaccess)