import os
import re
import requests
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    login_errors = db.Column(db.Integer, default=0)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

with app.app_context():
    db.create_all()

def validate_password(p):
    return len(p) >= 3 and any(c.isdigit() for c in p)

def validate_name(n):
    return re.match(r"^[A-Za-z0-9]{5,}$", n)

def verify_captcha(token):
    r = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={"secret": RECAPTCHA_SECRET_KEY, "response": token}
    )
    return r.json().get("success", False)

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    need_captcha = False

    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()

        if user:
            if user.login_errors >= 3:
                need_captcha = True
                if not verify_captcha(request.form.get("g-recaptcha-response", "")):
                    error = "Captcha inválido"
                    return render_template("login.html", error=error, sitekey=RECAPTCHA_SITE_KEY, captcha=True)

            if check_password_hash(user.password, request.form["password"]):
                user.login_errors = 0
                db.session.commit()
                session["user"] = user.id
                return redirect("/dashboard")
            else:
                user.login_errors += 1
                db.session.commit()
                error = "Senha incorreta"
        else:
            error = "Usuário não existe"

    return render_template("login.html", error=error, sitekey=RECAPTCHA_SITE_KEY, captcha=need_captcha)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        if not validate_name(u):
            error = "Nome inválido"
        elif not validate_password(p):
            error = "Senha fraca"
        elif User.query.filter_by(username=u).first():
            error = "Já existe um usuário com esse nome"
        else:
            user = User(username=u, password=generate_password_hash(p))
            db.session.add(user)
            db.session.commit()
            session["user"] = user.id
            return redirect("/dashboard")

    return render_template("register.html", error=error)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    services = Service.query.filter_by(user_id=session["user"]).all()
    return render_template("dashboard.html", services=services)

@app.route("/service/create", methods=["POST"])
def create_service():
    name = request.form["name"]
    if not validate_name(name):
        return redirect("/dashboard")

    exists = Service.query.filter_by(name=name).first()
    if not exists:
        s = Service(name=name, user_id=session["user"])
        db.session.add(s)
        db.session.commit()

    return redirect("/dashboard")

@app.route("/service/<int:id>", methods=["GET", "POST"])
def service(id):
    s = Service.query.get_or_404(id)

    if request.method == "POST":
        s.message = request.form["message"]
        db.session.commit()

    return render_template("service.html", service=s)

@app.route("/link/<service>/getmsg")
def getmsg(service):
    s = Service.query.filter_by(name=service).first()
    if not s or not s.message:
        return ""

    msg = s.message
    s.message = None
    db.session.commit()
    return f"<color=red>[playername]</color>: {msg}"

if __name__ == "__main__":
    app.run()
