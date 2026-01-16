import os
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "secret")

users = {}
services = {}
messages = {}

def valid_user(name):
    return len(name) >= 6 and name.isalnum()

def valid_pass(p):
    return len(p) >= 3 and any(c.isdigit() for c in p)

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u = request.form["user"]
        p = request.form["password"]
        if u in users and users[u]["password"] == p:
            session["user"] = u
            return redirect("/dashboard")
        error = "Login inválido"
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        u = request.form["user"]
        p = request.form["password"]
        if u in users:
            error = "Usuário já existe"
        elif not valid_user(u):
            error = "Usuário inválido"
        elif not valid_pass(p):
            error = "Senha inválida"
        else:
            users[u] = {"password": p, "services": []}
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
    if name not in services:
        services[name] = session["user"]
        messages[name] = None
        users[session["user"]]["services"].append(name)
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
