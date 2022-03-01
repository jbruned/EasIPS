# WordPress Docker Container
WordPress docker-compose.yml template is inspired by:  
>https://tecadmin.net/docker-compose-for-mysql-with-phpmyadmin/

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
## Links and information

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

### Volumes

The volume of /var/www/html of the Wordpress container is now found in 
>./webserver

The volume of for the MySQL container can be found in 
>./database

<br/>

### Logs

Logs can be found in 
TODO: Find logs
Apache logs are in /var/logs/apache. But these do not suffice