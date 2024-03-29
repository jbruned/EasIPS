import hashlib
import json
from logging import getLogger, CRITICAL

from flask import Flask, send_file, abort, request, redirect, session, url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from easips.core import ProtectedService, BackgroundIPS
from easips.db import ServiceSettings, AppSettings
from easips.log import log_warning
from easips.util import InvalidSettingsException, NotFoundException, ip_addr_is_valid


class WebGUI:
    """
    Contains the implementation of the entire administration web GUI
    """

    _DEFAULT_ADMIN_PASSWORD = "admin"
    _PASSWORD_SALT = "07fb9ac85a8a2480355aa66e1c958f97"

    def __init__(self, ips_instance: BackgroundIPS, db: SQLAlchemy):
        """
        Implementation of the WebGUI and all endpoints using Flask
        @param ips_instance: thread which runs the IPS in the background and contains the ProtectedService list
        @param db: database where all data is persisted
        """
        self.ips_instance = ips_instance
        self.app = Flask(__name__)
        getLogger('werkzeug').setLevel(CRITICAL)
        # Database configuration
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///easips.db?check_same_thread=False'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
        db.init_app(self.app)
        self.app.app_context().push()
        # Set the secret key for the Flask sessions
        self.app.secret_key = "c8648b0928e1a460370d30056520f265"
        # Initialize database
        Migrate(self.app, db)
        db.create_all()
        # Load app settings from the database
        settings_query = AppSettings.query
        # To restore default settings, uncomment this line:
        # settings_query.delete()
        if not settings_query.all():
            db.session.add(AppSettings(
                admin_password=self.get_hashed_password(self._DEFAULT_ADMIN_PASSWORD)
            ))  # Create default app configuration on first startup
            db.session.commit()
        self.settings = AppSettings.query.first()
        # Warn about the default password if needed
        if self.is_password_correct(self._DEFAULT_ADMIN_PASSWORD):
            log_warning(f"Admin password is set to default: {self._DEFAULT_ADMIN_PASSWORD}\n"
                        "          Please change it from the GUI")

        # Define Flask endpoints (both views and API endpoints)
        @self.app.route('/')
        def dashboard():
            if self.ip_is_blocked(request.remote_addr):
                return send_file('web/blocked_temp.html'), 403
            if not self.logged_in():
                return send_file("web/login.html")
            return send_file("web/dashboard.html")

        @self.app.route('/login', methods=['POST'])
        def login():
            if self.is_password_correct(request.form['password'], request.remote_addr):
                session["admin"] = "admin"
            return redirect(url_for('dashboard'))

        @self.app.route('/API/password', methods=['POST'])
        def change_password():
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            if not request.form['old'] or len(request.form['new'] or '') < 5 or len(request.form['repeat'] or '') < 5 \
                    or request.form['new'] != request.form['repeat']:
                abort(400)
            if not self.is_password_correct(request.form['old'], request.remote_addr):
                abort(401)
            self.settings.admin_password = self.get_hashed_password(request.form['new'])
            db.session.merge(self.settings)
            db.session.commit()
            return "", 200

        @self.app.route('/logout')
        def logout():
            session.pop("admin", None)
            return redirect(url_for("dashboard"))

        @self.app.route('/service/<service_id>')
        def service(service_id):
            if not self.logged_in():
                return redirect(url_for('dashboard'))
            if self.ip_is_blocked(request.remote_addr):
                return send_file('web/blocked_temp.html'), 403
            try:
                self.ips_instance.get_service(int(service_id))
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)
            return send_file("web/service.html")

        @self.app.route('/API/services/', methods=['GET', 'POST'])
        @self.app.route('/API/services/<service_id>', methods=['GET', 'POST', 'DELETE'])
        def api_service(service_id=None):
            if not self.logged_in():
                abort(401)
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                if service_id is not None:
                    service_id = int(service_id)
                if request.method == 'GET':
                    return json.dumps(self.ips_instance.get_service(service_id).get_info()
                                      if service_id else self.ips_instance.get_services_info(), default=str)
                elif request.method == 'POST':
                    data = request.form
                    service_type = (data['service'] if 'service' in data else '').lower()
                    if service_id is not None and (service_type is None or service_type == '') \
                            and self.ips_instance.get_service(service_id).settings.service == 'easips':
                        service_type = 'easips'
                    if not (service_type and int(data['max_attempts']) > 0 and int(data['time_threshold']) > 0
                            and data['log_path'] and (data['lock_resource'] or service_type == 'easips')
                            and ProtectedService.is_service_name_valid(service_type)):
                        abort(400)
                    s = self.ips_instance.get_service(service_id).settings if service_id else ServiceSettings()
                    s.name = data['name'] or service_type + " server"
                    s.service = service_type
                    s.time_threshold = data['time_threshold']
                    s.max_attempts = data['max_attempts']
                    s.block_duration = data['block_duration'] or None
                    s.log_path = data['log_path'] or None
                    s.lock_resource = data['lock_resource'] or None
                    if service_id is None:
                        s.stopped = False
                    try:
                        if service_id:
                            self.ips_instance.get_service(service_id).flag_as_modified()
                        else:
                            self.ips_instance.add_service(s)
                    except InvalidSettingsException:
                        abort(418)
                    return str(s.id), 200
                elif request.method == 'DELETE':
                    if self.ips_instance.get_service(service_id).settings.service == 'easips':
                        abort(401)
                    self.ips_instance.del_service(service_id)
                    return str(service_id), 200
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/playpause', methods=['POST'])
        def toggle_running(service_id):
            if not self.logged_in():
                abort(401)
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                self.ips_instance.get_service(int(service_id)).toggle_stopped()
                return str(service_id), 200
            except InvalidSettingsException:
                abort(418)
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/blocked', methods=['POST'])
        def block_unblock(service_id):
            if not self.logged_in():
                abort(401)
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                s = self.ips_instance.get_service(int(service_id))
                if not s.are_components_initialized():
                    abort(418)
                data = request.form
                if not ip_addr_is_valid(data['ip_address'] or ''):
                    raise ValueError
                if data['block'] == 'false':
                    s.unblock(data['ip_address'], db)
                else:
                    s.block(data['ip_address'], db)
                return str(s.settings.id), 200
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/static', methods=['POST'])
        def add_static_rule(service_id):
            if not self.logged_in():
                abort(401)
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                s = self.ips_instance.get_service(int(service_id))
                if not s.are_components_initialized():
                    abort(418)
                data = request.form
                if not ip_addr_is_valid(data['ip_address'] or ''):
                    raise ValueError
                s.create_static_rule(data['ip_address'], data['block'] == 'true', db)
                return 'OK', 200
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/static', methods=['DELETE'])
        def remove_static_rule(service_id):
            if not self.logged_in():
                abort(401)
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                s = self.ips_instance.get_service(int(service_id))
                if not s.are_components_initialized():
                    abort(418)
                data = request.form
                if not ip_addr_is_valid(data['ip_address'] or ''):
                    raise ValueError
                s.remove_static_rule(data['ip_address'], db)
                return 'OK', 200
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/static', methods=['GET'])
        def whitelist_blacklist(service_id):
            if not self.logged_in():
                abort(401)
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                s = self.ips_instance.get_service(int(service_id))
                return json.dumps(s.get_static_rules()), 200
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/blocked', methods=['GET'])
        def blocked_ips(service_id):
            if not self.logged_in():
                abort(401)
            if self.ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                return json.dumps(self.ips_instance.get_service(int(service_id)).get_blocked_ips(
                    historic=True), default=str)
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/assets/<filename>')
        def asset(filename):
            try:
                while '../' in filename:
                    filename = filename.replace('../', '')
                return send_file(f"web/assets/{filename}")
            except FileNotFoundError:
                abort(404)

    def get_hashed_password(self, password: str) -> str:
        """
        Returns the hash for the input password, using SHA-256 and a fixed salt
        @param password: original password
        @return: hashed password
        """
        return hashlib.sha256((password + self._PASSWORD_SALT).encode()).hexdigest()

    def is_password_correct(self, password: str, ip_addr=None) -> bool:
        """
        Checks the provided password against the hash; if it's not correct and the ip address is provided,
        the failed attempt is logged into the log file
        @param password: input password
        @param ip_addr: source IP address (optional, it's logged in case of error)
        @return: True if the password is correct, False otherwise
        """
        if self.get_hashed_password(password) == self.settings.admin_password:
            return True
        if ip_addr is not None:
            log_warning(f"Failed login attempt to the admin panel from {str(ip_addr).lower()}")
        return False

    # noinspection PyMethodMayBeStatic
    def logged_in(self) -> bool:
        """
        Checks if the user has started a session by entering the password
        @return: True if the user is logged in
        """
        return session.get("admin") is not None

    def ip_is_blocked(self, ip_addr) -> bool:
        """
        Checks if a certain IP address is blocked from the EasIPS web GUI
        @param ip_addr: IP address to check
        @return: True if the IP is blocked, False otherwise
        """
        return self.ips_instance.get_easips_service().is_blocked(str(ip_addr).lower())
