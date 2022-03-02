from flask import Flask, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///easips.db'
db = SQLAlchemy(app)

# so as DB needs to be defined to make models, I'm afraid I need to make the models here. Sorry
class Settings(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   time = db.Column(db.Integer, nullable=False)
   tries = db.Column(db.Integer, nullable=False)
   block_len = db.Column(db.Integer, nullable=True)  # null means infinite


class IPLoginTry(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   ip = db.Column(db.String(30), nullable=False)  # IPv6 has 29 characters, make sure we can store that
   moment = db.Column(db.DateTime(), nullable=False)


class BlockedIP(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   ip = db.Column(db.String(30), nullable=False)
   blocked_at = db.Column(db.DateTime(), nullable=True)  # null means infinitely blocked


migrate = Migrate(app, db)

if not Settings.query.all():
   db.session.add(Settings(
         id=1,
         time=1,
         tries=10,
         block_len=60
      ))  # default: block for an hour after 10 tries in 1 minute
   db.session.commit()
settings = Settings.query.order_by(Settings.id).first()


@app.route('/')
def dashboard():
   return send_file("web/dashboard.html")
   
@app.route('/service/<id>')
def service(id):
   return send_file("web/service.html")
   
@app.route('/assets/<filename>')
def asset(filename):
   return send_file(f"web/assets/{filename}")

# TODO: implement API using Flask with two GET endpoints:
# - /services/ -> Return a list of services in JSON (fields: service id, name,
#                 blocked IPs, both currently and past 24h, minutes since last block)
# - /services/{id} -> Return a list of blocked IPs in JSON (fields: address,
#                     minutes since block started)

# Flask should also have POST endpoints to receive AJAX requests (unblock IPs, create services...)
