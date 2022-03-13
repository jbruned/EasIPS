from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class AppSettings(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    admin_password = db.Column(db.String(50), nullable=False)  # e.g.: Public Blog Server / Internal SSH Server


class ServiceSettings(db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g.: Public Blog Server / Internal SSH Server
    service = db.Column(db.String(50), nullable=False)  # e.g.: Joomla / SSH
    time_threshold = db.Column(db.Integer, nullable=False)  # IP will be blocked if [max_attempts]
    max_attempts = db.Column(db.Integer, nullable=False)  # exceeded within [time_threshold]
    block_duration = db.Column(db.Integer, nullable=True)  # null means infinite
    log_path = db.Column(db.String(150), nullable=True)
    lock_resource = db.Column(db.String(150), nullable=True)  # If numeric: port, if contains /: web path, else: daemon
    stopped = db.Column(db.Boolean, nullable=False)


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id', ondelete='CASCADE'), nullable=False)
    ip_addr = db.Column(db.String(30), nullable=False)  # IPv6 has 29 characters, make sure we can store that
    timestamp = db.Column(db.DateTime, nullable=False)


class BlockedIP(db.Model):
    __tablename__ = "blocked_ips"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id', ondelete='CASCADE'), nullable=False)
    ip_addr = db.Column(db.String(30), nullable=False)
    blocked_at = db.Column(db.DateTime, nullable=True)  # null means infinitely blocked
    active = db.Column(db.Boolean, nullable=False)
