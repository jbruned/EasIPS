# WordPress Docker Container
WordPress docker-compose.yml template is inspired by: https://docs.docker.com/samples/wordpress/

# General Information

## Commands of setting up the containers
Setup WordPress
```
sudo docker compose up -d
```

Shutdown Wordpress container and MySQL container
```
sudo docker compose down
```
## Installation

Website to access PHPMyAdmin webserver:
><localhost:8083>

Setup the website

Title:
>Network Security

Username:
>user

Password:
>user

Check Confirm use of weak password

Email
>user@gmail.com

Press Install WordPress

## Volumes

The volume of /var/www/html of the Wordpress container is now found in 
>./webserver/var/www/html

The volume of /var/logs of Wordpress container can be found in
>./webserver/var/log

The volume of for the MySQL container can be found in 
>./database

<br/>

## Logs
Apache 2 Logs can be found at 
>[./webserver/var/log/apache2/access.log](./webserver/var/log/apache2/access.log)

The .htaccess can be found in 
>[./webserver/var/www/html/.htaccess](./webserver/var/www/html/.htaccess)