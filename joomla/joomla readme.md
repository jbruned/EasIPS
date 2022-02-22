# Joomla Docker Container

joomla-docker tutorial used: 
>https://www.hamrodev.com/en/app-development/joomla-docker-tutorial



# General Information

## Commands of setting up the containers
Setup joomla container and mysql container
```
sudo docker compose up -d
```

Shutdown joomla container and mysql container
```
sudo docker compose down
```
## Links and information

Website to configure Joomla webserver:
><localhost:8081>

URL for administrator Pannel
><localhost:8081/administrator>

Use the following login information:
Username: 
> superuser
Password:
> superuser123


### Volumes

The volume of the joomla container is now found in 
>./webserver

The volume of for the mysql container can be found in 
>./database


<br/>

### Logs

Logs can be found in 
>./webserver/administrator/logs


# Set By Step Installation

Setting up the containers

## 1. Setup containers
Run command
> sudo docker-compose up -d

<br/>

## 2. Install Joomla

<br/>

### 2a. Go to <localhost:8081>

<br/>

### 2b. Use the following configurations:

**Configuration of website**

Site name:
> Network Security

**Configurations of super user:**

Real Name: 
>Super User

Username: 
>superuser

Password: 
>superuser123

Email: 
>superuser123@gmail.com

<br/>

**Current MySQl Setup**

Database Type
>MySQLi

Host Name
>joomladb

Username
>root

Password
>root

Database Name
>joomladb

Table Prefix
>rbew3_

Connection Encryption
>Default

<br/>

## 3. Setup SSH

### I have some problems with this :(
### This keeps giving me an: Unable to connect to port 443 error.

### 3a. Go to <localhost:8081/administrator>

### 3b. Use the following login credentials to login:

Username: 
> superuser
> 
Password
> superuser123

### 3c. Go to system->Global Configurations->Server

### 3d. Set Force HTTPS to *Administrator only*

### 3e. Save and Close

