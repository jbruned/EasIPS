# PHPMyAdmin Docker Container
PHPMyAdmin docker-compose.yml template is inspired by:  
>https://tecadmin.net/docker-compose-for-mysql-with-phpmyadmin/

# General Information

## Commands of setting up the containers
Setup PHPMyAdmin
```
sudo docker compose up -d
```

Shutdown PHPMyAdmin container and mysql container
```
sudo docker compose down
```
## Links and information

Website to access PHPMyAdmin webserver:
><localhost:8082>


Use the following login information:
Username: 
> root

Password:
> root

### Volumes

The volume of /var/log of the PHPMyAdmin container is now found in 
>./webserver

The volume of for the mysql container can be found in 
>./database

<br/>

### Logs

Logs can be found in 
>./webserver/log/apache2/