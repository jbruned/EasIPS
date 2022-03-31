from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class AppSettings(db.Model):
    """
    Stores the EasIPS application settings (currently only the admin password)
    There must only exist one object of this type (one row in the corresponding table)
    """
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    admin_password = db.Column(db.String(64), nullable=False)  # sha256 hash is 64 chars long (256 bytes)


class ServiceSettings(db.Model):
    """
    Stores a ProtectedService's settings
    """
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g.: Public Blog Server / Internal SSH Server
    service = db.Column(db.String(50), nullable=False)  # joomla / ssh / wordpress / phpmyadmin / easips
    time_threshold = db.Column(db.Integer, nullable=False)
    max_attempts = db.Column(db.Integer, nullable=False)
    block_duration = db.Column(db.Integer, nullable=True)  # null means infinite
    log_path = db.Column(db.String(150), nullable=True)
    lock_resource = db.Column(db.String(150), nullable=True)  # numeric? port, contains '/'? web path, else? daemon
    stopped = db.Column(db.Boolean, nullable=False)


class LoginAttempt(db.Model):
    """
    Stores a login attempt from an IP and a ProtectedService
    """
    __tablename__ = "login_attempts"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id', ondelete='CASCADE'), nullable=False)
    ip_addr = db.Column(db.String(30), nullable=False)  # IPv6 has 29 characters, make sure we can store that
    timestamp = db.Column(db.DateTime, nullable=False)


class BlockedIP(db.Model):
    """
    Stores a blocked IP from a ProtectedService
    """
    __tablename__ = "blocked_ips"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id', ondelete='CASCADE'), nullable=False)
    ip_addr = db.Column(db.String(30), nullable=False)
    blocked_at = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean, nullable=False)


class StaticRule(db.Model):
    """
    Stores a whitelist/blacklist rule for and IP and a ProtectedService
    """
    __tablename__ = "static_rules"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id', ondelete='CASCADE'), nullable=False)
    ip_addr = db.Column(db.String(30), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False)
    blocked = db.Column(db.Boolean, nullable=False)
