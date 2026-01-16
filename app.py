import os
import time
import re
import requests
from flask import Flask, request, render_template_string, redirect

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-key")

# ===== reCAPTCHA (VARIÁVEIS EXTERNAS) =====
SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

if not SITE_KEY or not SECRET_KEY:
    raise RuntimeError("Defina RECAPTCHA_SITE_KEY e RECAPTCHA_SECRET_KEY nas variáveis de ambiente")

# ===== DADOS EM MEMÓRIA =====
usuarios = {}        # nome -> senha
servicos = {}        # servico -> usuario
mensagens = {}       # servico -> mensagem
tentativas = {}      # nome -> erros

# ===== BASE HTML + CSS =====
BASE_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Cabeça de bago, canela de angu, ce fala que gosta e eu como seu ku</title>
<script src="https://www.google.com/recaptcha/api.js" async defer></script>
<style>
* { box-sizing: border-box; font-family: Arial, Helvetica, sans-serif; }
body {
    background: #f1f5f9;
    margin: 0;
    height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}
.card {
    background: #ffffff;
    padding: 32px;
    width: 380px;
    border-radius: 12px;
    box-shadow: 0 10px 35px rgba(0,0,0,.12);
}
h2 { text-align: center; margin-top: 0; }
input {
    width: 100%;
    padding: 10px;
    margin: 8px 0 14px 0;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
}
button {
    width: 100%;
    padding: 10px;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 15px;
    cursor: pointer;
}
button:hover { background: #1d4ed8; }
.msg-erro { color: #dc2626; text-align: center; }
.msg-ok { color: #16a34a; text-align: center; }
small { display: block; text-align: center; margin-top: 14px; }
code {
    display: block;
    background: #e5e7eb;
    padding: 8px;
    border-radius: 6px;
    text-align: center;
    font-size: 13px;
}
</style>
</head>
<body>
<div class="card">
{{ content }}
</div>
</body>
</html>
"""

# ===== TELAS =====

CADASTRO_HTML = """
<h2>Criar Conta</h2>
<form method="post">
<input name="nome" placeholder="Nome de usuário" required>
<input name="senha" type="password" placeholder="Senha" required>
<button>Criar Conta</button>
</form>
<p class="msg-erro">{{ erro }}</p>
<small><a href="/login">Já tenho conta</a></small>
"""

SERVICO_HTML = """
<h2>Nome do Serviço</h2>
<form method="post">
<input name="servico" placeholder="Nome do serviço" required>
<button>Criar Serviço</button>
</form>
<p class="msg-erro">{{ erro }}</p>
"""

LOGIN_HTML = """
<h2>Login</h2>
<form method="post">
<input name="nome" placeholder="Usuário" required>
<input name="senha" type="password" placeholder="Senha" required>

{% if captcha %}
<div class="g-recaptcha" data-sitekey="{{ site_key }}"></div><br>
{% endif %}

<button>Entrar</button>
</form>
<p class="msg-erro">{{ erro }}</p>
"""

PAINEL_HTML = """
<h2>Painel</h2>
<form method="post">
<input name="mensagem" placeholder="Digite a mensagem">
<button>Enviar</button>
</form>

<p class="msg-ok">{{ ok }}</p>

<p>Endpoint:</p>
<code>/link/{{ servico }}/getmsg</code>
"""

# ===== ROTAS =====

@app.route("/", methods=["GET", "POST"])
def cadastro():
    erro = ""
    if request.method == "POST":
        nome = request.form["nome"]
        senha = request.form["senha"]

        if nome in usuarios:
            erro = "Já existe um usuário com esse nome"
        elif len(nome) < 5:
            erro = "O nome precisa ter pelo menos 5 letras"
        elif len(senha) < 3 or not re.search(r"\\d", senha):
            erro = "A senha precisa ter pelo menos 3 caracteres e um número"
        else:
            usuarios[nome] = senha
            tentativas[nome] = 0
            return redirect(f"/servico/{nome}")

    return render_template_string(BASE_HTML, content=render_template_string(CADASTRO_HTML, erro=erro))

@app.route("/servico/<nome>", methods=["GET", "POST"])
def criar_servico(nome):
    erro = ""
    if nome not in usuarios:
        return "Usuário inválido"

    if request.method == "POST":
        servico = request.form["servico"]
        if servico in servicos:
            erro = "Já existe um serviço com esse nome"
        else:
            servicos[servico] = nome
            mensagens[servico] = None
            return redirect(f"/painel/{servico}")

    return render_template_string(BASE_HTML, content=render_template_string(SERVICO_HTML, erro=erro))

@app.route("/login", methods=["GET", "POST"])
def login():
    erro = ""
    captcha = False
    nome = request.form.get("nome", "")

    if tentativas.get(nome, 0) >= 3:
        captcha = True

    if request.method == "POST":
        senha = request.form["senha"]

        if captcha:
            token = request.form.get("g-recaptcha-response")
            if not token:
                erro = "Confirme o captcha"
            else:
                r = requests.post(
                    "https://www.google.com/recaptcha/api/siteverify",
                    data={"secret": SECRET_KEY, "response": token}
                ).json()
                if not r.get("success"):
                    erro = "Captcha inválido"

        if not erro:
            if nome not in usuarios or usuarios[nome] != senha:
                tentativas[nome] = tentativas.get(nome, 0) + 1
                erro = "Usuário ou senha incorretos"
            else:
                tentativas[nome] = 0
                return redirect(f"/painel/{get_servico(nome)}")

    return render_template_string(
        BASE_HTML,
        content=render_template_string(LOGIN_HTML, erro=erro, captcha=captcha, site_key=SITE_KEY)
    )

def get_servico(nome):
    for s, u in servicos.items():
        if u == nome:
            return s
    return ""

@app.route("/painel/<servico>", methods=["GET", "POST"])
def painel(servico):
    if servico not in servicos:
        return "Serviço inválido"

    ok = ""
    if request.method == "POST":
        mensagens[servico] = request.form["mensagem"]
        ok = "Mensagem enviada com sucesso"

    return render_template_string(BASE_HTML, content=render_template_string(PAINEL_HTML, servico=servico, ok=ok))

# ===== WEBREQUEST (ESTILO LAC) =====

@app.route("/link/<servico>/getmsg")
def getmsg(servico):
    inicio = time.time()

    while time.time() - inicio < 3:
        if mensagens.get(servico):
            msg = mensagens[servico]
            mensagens[servico] = None
            return f"|| MENSAGEM || : {msg}"
        time.sleep(0.1)

    return ""

# ===== MAIN =====

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
