import os
import time
import re
import requests
from flask import Flask, request, render_template_string, redirect, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "chave-secreta-padrao-dev")

SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

db_usuarios = {}
db_servicos = {}
db_mensagens = {}
db_tentativas = {}

BASE_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sistema de Mensagens</title>
<script src="https://www.google.com/recaptcha/api.js" async defer></script>
<style>
* { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
body { background: #f8fafc; margin: 0; height: 100vh; display: flex; justify-content: center; align-items: center; color: #334155; }
.card { background: #ffffff; padding: 2rem; width: 100%; max-width: 400px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
h2 { text-align: center; margin-top: 0; color: #0f172a; }
input { width: 100%; padding: 0.75rem; margin: 0.5rem 0 1rem 0; border: 1px solid #cbd5e1; border-radius: 6px; outline: none; transition: border-color 0.2s; }
input:focus { border-color: #2563eb; }
button { width: 100%; padding: 0.75rem; background: #2563eb; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
button:hover { background: #1d4ed8; }
.btn-secondary { background: #64748b; margin-top: 10px; }
.btn-secondary:hover { background: #475569; }
.msg-erro { color: #dc2626; text-align: center; font-size: 0.9rem; margin-top: 1rem; }
.msg-ok { color: #16a34a; text-align: center; font-size: 0.9rem; margin-top: 1rem; }
small { display: block; text-align: center; margin-top: 1rem; font-size: 0.875rem; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
code { display: block; background: #f1f5f9; padding: 0.75rem; border-radius: 6px; text-align: center; font-size: 0.85rem; word-break: break-all; margin-top: 0.5rem; color: #475569; border: 1px dashed #cbd5e1; }
.label-cod { font-size: 0.8rem; font-weight: bold; text-align: center; display: block; margin-top: 1rem; }
</style>
</head>
<body>
<div class="card">
{{ content }}
</div>
</body>
</html>
"""

CADASTRO_HTML = """
<h2>Criar Conta</h2>
<form method="post">
    <input name="nome" placeholder="Nome de usuário" required>
    <input name="senha" type="password" placeholder="Senha" required>
    <button>Cadastrar</button>
</form>
{% if erro %}
<p class="msg-erro">{{ erro }}</p>
{% endif %}
<small><a href="/login">Já tenho uma conta</a></small>
"""

LOGIN_HTML = """
<h2>Login</h2>
<form method="post">
    <input name="nome" placeholder="Usuário" required>
    <input name="senha" type="password" placeholder="Senha" required>
    {% if captcha %}
    <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
        <div class="g-recaptcha" data-sitekey="{{ site_key }}"></div>
    </div>
    {% endif %}
    <button>Entrar</button>
</form>
{% if erro %}
<p class="msg-erro">{{ erro }}</p>
{% endif %}
<small><a href="/">Criar nova conta</a></small>
"""

CRIAR_SERVICO_HTML = """
<h2>Novo Serviço</h2>
<p style="text-align:center; margin-bottom:1rem">Crie um identificador para receber mensagens.</p>
<form method="post">
    <input name="servico" placeholder="Nome do serviço (ex: alerta01)" required>
    <button>Ativar Serviço</button>
</form>
{% if erro %}
<p class="msg-erro">{{ erro }}</p>
{% endif %}
<small><a href="/logout">Sair</a></small>
"""

PAINEL_HTML = """
<h2>Painel de Controle</h2>
<p style="text-align:center; color:#64748b">Serviço: <strong>{{ servico }}</strong></p>
<form method="post">
    <input name="mensagem" placeholder="Digite a mensagem para enviar" required>
    <button>Enviar Mensagem</button>
</form>
{% if ok %}
<p class="msg-ok">{{ ok }}</p>
{% endif %}
<span class="label-cod">Seu Endpoint:</span>
<code>{{ url_endpoint }}</code>
<form action="/logout" method="get">
    <button class="btn-secondary">Sair</button>
</form>
"""

@app.route("/", methods=["GET", "POST"])
def cadastro():
    if "usuario" in session:
        return redirect(url_for("painel"))

    erro = None
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()

        if nome in db_usuarios:
            erro = "Usuário já existe."
        elif len(nome) < 4:
            erro = "O nome deve ter no mínimo 4 caracteres."
        elif len(senha) < 4 or not re.search(r"\d", senha):
            erro = "A senha deve ter no mínimo 4 caracteres e incluir um número."
        else:
            db_usuarios[nome] = senha
            db_tentativas[nome] = 0
            session["usuario"] = nome
            return redirect(url_for("painel"))

    return render_template_string(BASE_HTML, content=render_template_string(CADASTRO_HTML, erro=erro))

@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario" in session:
        return redirect(url_for("painel"))

    erro = None
    mostrar_captcha = False
    
    usuario_tentativa = request.form.get("nome", "")
    if usuario_tentativa in db_tentativas and db_tentativas[usuario_tentativa] >= 3:
        mostrar_captcha = True

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "").strip()

        if mostrar_captcha:
            token = request.form.get("g-recaptcha-response")
            if not token:
                erro = "Por favor, complete o Captcha."
            elif SITE_KEY and SECRET_KEY:
                validacao = requests.post(
                    "https://www.google.com/recaptcha/api/siteverify",
                    data={"secret": SECRET_KEY, "response": token}
                ).json()
                if not validacao.get("success"):
                    erro = "Captcha inválido."

        if not erro:
            if nome in db_usuarios and db_usuarios[nome] == senha:
                db_tentativas[nome] = 0
                session["usuario"] = nome
                return redirect(url_for("painel"))
            else:
                db_tentativas[nome] = db_tentativas.get(nome, 0) + 1
                erro = "Credenciais inválidas."
                if db_tentativas[nome] >= 3:
                    mostrar_captcha = True

    return render_template_string(
        BASE_HTML, 
        content=render_template_string(LOGIN_HTML, erro=erro, captcha=mostrar_captcha, site_key=SITE_KEY or "")
    )

@app.route("/criar-servico", methods=["GET", "POST"])
def criar_servico():
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    usuario_atual = session["usuario"]
    
    for s, u in db_servicos.items():
        if u == usuario_atual:
            return redirect(url_for("painel"))

    erro = None
    if request.method == "POST":
        novo_servico = request.form.get("servico", "").strip()
        if not re.match(r"^[a-zA-Z0-9_-]+$", novo_servico):
            erro = "Use apenas letras, números e hifens."
        elif novo_servico in db_servicos:
            erro = "Este nome de serviço já está em uso."
        else:
            db_servicos[novo_servico] = usuario_atual
            db_mensagens[novo_servico] = None
            return redirect(url_for("painel"))

    return render_template_string(BASE_HTML, content=render_template_string(CRIAR_SERVICO_HTML, erro=erro))

@app.route("/painel", methods=["GET", "POST"])
def painel():
    if "usuario" not in session:
        return redirect(url_for("login"))

    usuario = session["usuario"]
    servico_usuario = None
    
    for s, u in db_servicos.items():
        if u == usuario:
            servico_usuario = s
            break
    
    if not servico_usuario:
        return redirect(url_for("criar_servico"))

    msg_ok = None
    if request.method == "POST":
        msg = request.form.get("mensagem")
        if msg:
            db_mensagens[servico_usuario] = msg
            msg_ok = "Mensagem enviada para a fila!"

    full_endpoint = f"{request.host_url}link/{servico_usuario}/getmsg"
    
    return render_template_string(
        BASE_HTML, 
        content=render_template_string(PAINEL_HTML, servico=servico_usuario, ok=msg_ok, url_endpoint=full_endpoint)
    )

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

@app.route("/link/<servico_nome>/getmsg")
def getmsg(servico_nome):
    if servico_nome not in db_servicos:
        return "Servico Inexistente", 404

    tempo_limite = time.time() + 3
    
    while time.time() < tempo_limite:
        msg = db_mensagens.get(servico_nome)
        if msg:
            db_mensagens[servico_nome] = None
            return f"|| MENSAGEM || : {msg}"
        time.sleep(0.2)

    return ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
