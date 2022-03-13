import json
from logging import getLogger, CRITICAL

from flask import Flask, send_file, abort, request, redirect, send_from_directory, session
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from easips.core import ProtectedService, BackgroundIPS
from easips.db import ServiceSettings, AppSettings
from easips.log import log_warning
from easips.util import InvalidSettingsException, NotFoundException


import hashlib


class WebGUI:

    _DEFAULT_ADMIN_PASSWORD = "admin"

    def __init__(self, ips_instance: BackgroundIPS, db: SQLAlchemy):
        

        self.ips_instance = ips_instance
        self.app = Flask(__name__)
        getLogger('werkzeug').setLevel(CRITICAL)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///easips.db?check_same_thread=False'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
        db.init_app(self.app)
        self.app.app_context().push()
        #We first have to set the secret key for the session
        self.app.secret_key = "super secret key" 

        Migrate(self.app, db)
        db.create_all()

        def get_hashed_password(password: str) -> str:
            password = hashlib.md5(password.encode()).hexdigest()
            return password  

        def is_password_correct(password: str, ip_addr=None) -> bool:
            correct = (get_hashed_password(password) == self.settings.admin_password)  
            if not correct and ip_addr is not None:
                log_warning(f"Failed login attempt from {str(ip_addr).lower()}")
            return correct
        

        settings_query = AppSettings.query
        if not settings_query.all():

            db.session.add(AppSettings(
                admin_password=get_hashed_password(self._DEFAULT_ADMIN_PASSWORD)
            ))  # load default app config on first run
            db.session.commit()
        self.settings = AppSettings.query.first()

        if is_password_correct(self._DEFAULT_ADMIN_PASSWORD):
            log_warning(f"Admin password is set to default: {self._DEFAULT_ADMIN_PASSWORD}\n"
                        "          Please change it from the GUI")

        def logged_in():
            if session.get("admin") is None:
                return False  
            else:
                return True

        def ip_is_blocked(ip_addr):
            return self.ips_instance.get_easips_service().is_blocked(str(ip_addr).lower())

        @self.app.route('/')
        def dashboard():
            if not logged_in():
                return send_file("web/login.html")
            else:
                return send_file("web/dashboard.html")

        @self.app.route('/login', methods=['POST'])
        def login():
            if is_password_correct(request.form['password'], request.remote_addr):
                session["admin"] = "admin" 
            return redirect("/")

        @self.app.route('/API/password', methods=['POST'])
        def change_password():
            if ip_is_blocked(request.remote_addr):
                return send_file('web/blocked.html'), 403
            if not request.form['old'] or len(request.form['new'] or '') < 5 or len(request.form['repeat'] or '') < 5 \
                    or request.form['new'] != request.form['repeat']:
                abort(400)
            if not is_password_correct(request.form['old'], request.remote_addr):
                abort(401)
            self.settings.admin_password = get_hashed_password(request.form['new'])
            db.session.merge(self.settings)
            db.session.commit()
            return "", 200

        @self.app.route('/logout')
        def logout():
            session.pop("admin",None)
            return redirect("/")

        @self.app.route('/service/<service_id>')
        def service(service_id):
            if ip_is_blocked(request.remote_addr):
                abort(403)
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
            if ip_is_blocked(request.remote_addr):
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
            if ip_is_blocked(request.remote_addr):
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
            if ip_is_blocked(request.remote_addr):
                abort(403)
            try:
                s = self.ips_instance.get_service(int(service_id))
                if not s.are_components_initialized():
                    abort(418)
                data = request.form
                if data['block'] == 'false':
                    s.unblock(data['ip_address'], db)
                else:
                    s.block(data['ip_address'], db)
                return str(s.settings.id), 200
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/blocked', methods=['GET'])
        def blocked_ips(service_id):
            if ip_is_blocked(request.remote_addr):
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
