# EasIPS: a modular Intrusion Prevention System

This repo contains the source code for *EasIPS*, an easy-to-use and customizable modular Intrusion Prevention System programmed in Python.

## General information

This software allows to dynamically block IPs who exceed a configurable number of failed login attempts in a customizable amount of time during an also user-defined time period.

These settings can be adjusted from the web-based graphical user interface, where blocked IPs and more information can also be listed.

### Supported services

- WordPress
- SSH
- Joomla
- phpMyAdmin

## Run instructions

It's enough to run the `main.py` file with the python interpreter, given that the *PIP* dependencies (`requirements.txt`) are satisfied.

This script will run the application in the background, as well as the web *GUI*; the listening address and port can be specified in the call.

## Project structure

- `/easips` for the Python package, including:
    - `locks.py` for `ServiceLock` and its implementations
    - `login_trackers.py` for `LoginTracker` and its implementations
    - `/web` for the static GUI files (HTML, CSS & JavaScript)
    - `gui.py` for the Flask application
    - `db.py` for the database and model creation
    - `core.py` for the main loop and service management
    - `app.py`, which contains the main class that needs to be instantiated and run (`EasIPS`)
- `/ssh`, `/joomla`, `/phpMyAdmin`, `/wordpress` for the different services
- `/tests` to store test python files
- `main.py`, which runs the whole application and the web GUI in the background

## Development

*EasIPS* has been developed for the 2022 Network Security Course from TU Delft's MSc Computer Science by:

- Jorge Bruned
- Thomas Werthenbach
- Job Kanis
- Cesar van der Poel
- Louise van der Peet
- Ane Zubillaga Argal
