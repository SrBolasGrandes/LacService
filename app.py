import os
import requests
from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "secret")

SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

users = {}
services = {}
messages = {}

def valid_user(u):
    return len(u) >= 6 and u.isalnum()

def valid_pass(p):
    return len(p) >= 3 and any(c.isdigit() for c in p)

def check_captcha(token):
    if not token:
        return False
    r = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={"secret": SECRET_KEY, "response": token}
    )
    return r.json().get("success", False)

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    show_captcha = False

    if request.method == "POST":
        u = request.form["user"]
        p = request.form["password"]
        user = users.get(u)

        if not user:
            error = "Login inválido"
        else:
            if user["errors"] >= 3:
                show_captcha = True
                if not check_captcha(request.form.get("g-recaptcha-response")):
                    return render_template("login.html", error="Captcha inválido", show_captcha=True, site_key=SITE_KEY)

            if user["password"] != p:
                user["errors"] += 1
                error = "Senha incorreta"
            else:
                user["errors"] = 0
                session["user"] = u
                return redirect("/dashboard")

    return render_template("login.html", error=error, show_captcha=show_captcha, site_key=SITE_KEY)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        u = request.form["user"]
        p = request.form["password"]

        if u in users:
            error = "Já existe um usuário com esse nome"
        elif not valid_user(u):
            error = "Usuário precisa ter letras e números (mín. 6)"
        elif not valid_pass(p):
            error = "Senha precisa ter 3 caracteres e um número"
        else:
            users[u] = {"password": p, "services": [], "errors": 0}
            session["user"] = u
            return redirect("/dashboard")

    return render_template("register.html", error=error)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html", services=users[session["user"]]["services"])

@app.route("/create_service", methods=["POST"])
def create_service():
    name = request.form["service"]
    u = session["user"]

    if name and name not in services:
        services[name] = u
        messages[name] = None
        users[u]["services"].append(name)

    return redirect("/dashboard")

@app.route("/service/<name>", methods=["GET", "POST"])
def service(name):
    if "user" not in session or services.get(name) != session["user"]:
        return redirect("/login")

    if request.method == "POST":
        messages[name] = request.form["msg"]

    return render_template("service.html", name=name)

@app.route("/link/<name>/getmsg")
def getmsg(name):
    msg = messages.get(name)
    if not msg:
        return ""
    messages[name] = None
    return f"|| MENSAGEM || : {msg}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
