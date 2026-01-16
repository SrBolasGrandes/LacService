import os
import re
import requests
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev_secret")

# reCAPTCHA (variáveis externas – Render)
SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

# Banco simples em memória (produção → use Postgres)
users = {}
messages = {}

def senha_valida(s):
    return len(s) >= 3 and any(c.isdigit() for c in s)

def nome_valido(n):
    return len(n) >= 5 and n.isalpha()

def verificar_captcha(token):
    if not token:
        return False
    r = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={"secret": SECRET_KEY, "response": token}
    )
    return r.json().get("success", False)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        nome = request.form["name"]
        senha = request.form["password"]

        if nome in users:
            error = "Já existe um usuário com esse nome"
        elif not nome_valido(nome):
            error = "Nome precisa ter pelo menos 5 letras"
        elif not senha_valida(senha):
            error = "Senha precisa ter 3 caracteres e um número"
        else:
            users[nome] = {
                "password": senha,
                "errors": 0,
                "service": None
            }
            session["user"] = nome
            return redirect(url_for("service"))

    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    show_captcha = False

    if request.method == "POST":
        nome = request.form["name"]
        senha = request.form["password"]

        user = users.get(nome)
        if not user:
            error = "Usuário não existe"
        else:
            if user["errors"] >= 3:
                show_captcha = True
                if not verificar_captcha(request.form.get("g-recaptcha-response")):
                    error = "Captcha inválido"
                    return render_template("login.html", error=error, show_captcha=True, site_key=SITE_KEY)

            if senha != user["password"]:
                user["errors"] += 1
                error = "Senha incorreta"
            else:
                user["errors"] = 0
                session["user"] = nome
                return redirect(url_for("service"))

    return render_template("login.html", error=error, show_captcha=show_captcha, site_key=SITE_KEY)

@app.route("/service", methods=["GET", "POST"])
def service():
    if "user" not in session:
        return redirect(url_for("login"))

    error = None
    if request.method == "POST":
        service_name = request.form["service"]

        if service_name in messages:
            error = "Já existe um serviço com esse nome"
        else:
            users[session["user"]]["service"] = service_name
            messages[service_name] = None
            return redirect(f"/link/{service_name}")

    return render_template("service.html", error=error)

@app.route("/link/<service>")
def link(service):
    if service not in messages:
        return "Serviço não encontrado", 404
    return f"Serviço ativo: {service}"

@app.route("/link/<service>/send", methods=["POST"])
def send(service):
    messages[service] = request.form.get("msg")
    return "OK"

@app.route("/link/<service>/getmsg")
def getmsg(service):
    msg = messages.get(service)
    if not msg:
        return ""
    messages[service] = None
    return f"|| MENSAGEM || : {msg}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
