from flask import Flask, send_file, abort, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from easips.db import db, ServiceSettings
from easips.core import ProtectedService, NotFoundException
from logging import getLogger, CRITICAL
import datetime
import json

class WebGUI:

    def __init__(self, ips_instance):
        self.ips_instance = ips_instance
        self.app = Flask(__name__)
        getLogger('werkzeug').setLevel(CRITICAL)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///easips.db?check_same_thread=False'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
        db.init_app(self.app)
        self.app.app_context().push()

        Migrate(self.app, db)
        db.create_all()

        #if not ServiceSettings.query.all():
        #db.session.add(ServiceSettings(
                #id=1,
                #name="Test service!",
                #service="Joomla",
                #time_threshold=1,
                #max_attempts=10,
                #block_duration=60,
                #stopped = False
            #))  # default: block for an hour after 10 tries in 1 minute
        #db.session.commit()
        #settings = ServiceSettings.query.order_by(ServiceSettings.id).first()

        @self.app.route('/')
        def dashboard():
            return send_file("web/dashboard.html")

        @self.app.route('/login', methods = ['GET', 'POST'])
        def login():
            if request.method == 'GET':
                return send_file("web/login.html")
            elif request.method == 'POST':
                password = request.form['password']
                # TODO: check password and start user session
                return "Auth is still not implemented"

        @self.app.route('/logout')
        def logout():
            # TODO: end user session
            return send_file("web/login.html")

        @self.app.route('/service/<service_id>')
        def service(service_id):
            return send_file("web/service.html")

        @self.app.route('/API/services/', methods = ['GET', 'POST'])
        @self.app.route('/API/services/<service_id>', methods = ['GET', 'POST', 'DELETE'])
        def api_service(service_id = None):
            try:
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
                    s.stopped = False
                    if service_id:
                        db.session.commit()
                    else:
                        self.ips_instance.add_service(s)
                    return str(s.id), 200
                elif request.method == 'DELETE':
                    self.ips_instance.del_service(service_id)
                    return str(service_id), 200
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/playpause', methods = ['POST'])
        def toggle_running(service_id):
            try:
                self.ips_instance.get_service(service_id).toggleStopped()
                db.session.commit()
                return str(service_id), 200
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/blocked', methods = ['POST'])
        def block_unblock(service_id):
            try:
                service = self.ips_instance.get_service(service_id)
                data = request.form
                if data['block'] == 'false':
                    service.unblock(data['ip_address'], db)
                else:
                    service.block(data['ip_address'], db)
                return str(service.settings.id), 200
            except NotFoundException:
                abort(404)

        @self.app.route('/API/services/<service_id>/blocked', methods = ['GET'])
        def blocked_ips(service_id):
            try:
                return json.dumps(self.ips_instance.get_service(service_id).get_blocked_ips(
                                  historic=True), default=str)
            except NotFoundException:
                abort(404)

        @self.app.route('/assets/<filename>')
        def asset(filename):
            try:
                return send_file(f"web/assets/{filename}")
            except FileNotFoundError:
                abort(404)

        # TODO: implement API using Flask with two GET endpoints:
        # - /services/ -> Return a list of services in JSON (fields: service id, name,
        #                 blocked IPs, both currently and past 24h, minutes since last block)
        # - /services/{id} -> Return a list of blocked IPs in JSON (fields: address,
        #                     minutes since block started)

        # Flask should also have POST endpoints to receive AJAX requests (unblock IPs, create services...)
