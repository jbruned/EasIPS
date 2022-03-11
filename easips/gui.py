import json
from logging import getLogger, CRITICAL

from flask import Flask, send_file, abort, request, redirect
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from easips.core import ProtectedService, NotFoundException, BackgroundIPS
from easips.db import ServiceSettings, AppSettings
from easips.util import InvalidSettingsException, NotFoundException


class WebGUI:

    def __init__(self, ips_instance: BackgroundIPS, db: SQLAlchemy):
        self.ips_instance = ips_instance
        self.app = Flask(__name__)
        getLogger('werkzeug').setLevel(CRITICAL)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///easips.db?check_same_thread=False'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
        db.init_app(self.app)
        self.app.app_context().push()

        Migrate(self.app, db)
        db.create_all()

        settings_query = AppSettings.query
        if not settings_query.all():
            db.session.add(AppSettings(
                admin_password="admin"  # TODO: hash
            ))  # default password is admin
            db.session.commit()
        self.settings = AppSettings.query.first()

        @self.app.route('/')
        def dashboard():
            logged_in = False  # TODO: check if logged in
            if not logged_in:
                send_file("web/login.html")
            return send_file("web/dashboard.html")

        @self.app.route('/login', methods=['POST'])
        def login():
            if request.form['password'] == self.settings.admin_password:  # TODO: check password hash instead
                pass  # TODO: start user session
            return redirect("/")

        @self.app.route('/logout')
        def logout():
            # TODO: end user session
            return redirect("/")

        @self.app.route('/service/<service_id>')
        def service(service_id):
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
            try:
                if service_id is not None:
                    service_id = int(service_id)
                if request.method == 'GET':
                    return json.dumps(self.ips_instance.get_service(service_id).get_info()
                                      if service_id else self.ips_instance.get_services_info(), default=str)
                elif request.method == 'POST':
                    data = request.form
                    service_type = data['service'].lower()
                    if not (service_type and data['max_attempts'] and
                            ProtectedService.is_service_valid(service_type, data['log_path'] or None,
                                                              data['web_path'] or None)):
                        abort(400)
                    s = self.ips_instance.get_service(service_id).settings if service_id else ServiceSettings()
                    s.name = data['name'] or service_type + " server"
                    s.service = service_type
                    s.time_threshold = data['time_threshold']
                    s.max_attempts = data['max_attempts']
                    s.block_duration = data['block_duration'] or None
                    s.log_path = data['log_path'] or None
                    s.web_path = data['web_path'] or None
                    try:
                        if service_id:
                            self.ips_instance.get_service(service_id).flag_as_modified()
                        else:
                            self.ips_instance.add_service(s)
                    except InvalidSettingsException:
                        abort(418)
                    return str(s.id), 200
                elif request.method == 'DELETE':
                    self.ips_instance.del_service(service_id)
                    return str(service_id), 200
            except ValueError:
                abort(400)
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/playpause', methods=['POST'])
        def toggle_running(service_id):
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
            try:
                s = self.ips_instance.get_service(int(service_id))
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
                return send_file(f"web/assets/{filename}")
            except FileNotFoundError:
                abort(404)
