import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE DE ELITE FINAL - BLINDADO ATIVO")

app = Flask(__name__)

# =========================
# CONFIG
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# BANCO
# =========================
def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessoes (
        telefone TEXT PRIMARY KEY,
        estado TEXT,
        nome TEXT,
        cpf TEXT,
        sintoma TEXT,
        horario TEXT,
        ultima_msg TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS agenda (
        id SERIAL PRIMARY KEY,
        hora TEXT,
        disponivel BOOLEAN DEFAULT TRUE
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

# =========================
# BLOQUEIO TOTAL (ANTI DESVIO)
# =========================
def fora_do_escopo(msg):
    palavras = [
        "dinheiro", "ganhar dinheiro", "acidente",
        "socorro", "morrendo", "urgente", "ajuda",
        "me ajuda", "emergencia", "emergência"
    ]
    return any(p in msg.lower() for p in palavras)

# =========================
# AUXILIARES
# =========================
def detectar_horario(msg):
    match = re.search(r'\b(0?[0-9]|1[0-9]|2[0-3])\b', msg)
    return match.group() if match else None

def validar_cpf(cpf):
    return len(re.sub(r'\D', '', cpf)) == 11

def enviar_whatsapp(telefone, mensagem):
    try:
        requests.post(
            f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
            json={"phone": telefone, "message": mensagem},
            timeout=10
        )
    except Exception as e:
        print("Erro WhatsApp:", e)

# =========================
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
    except:
        return "OK", 200

    if not data or data.get("fromMe"):
        return "OK", 200

    telefone = data.get("phone", "").split("@")[0]
    msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else data.get("message", "")

    if not telefone or not msg:
        return "OK", 200

    conn = conectar()
    cur = conn.cursor()

    # =========================
    # BUSCA SESSÃO
    # =========================
    cur.execute("SELECT * FROM sessoes WHERE telefone=%s", (telefone,))
    sessao = cur.fetchone()

    if not sessao:
        cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, 'TRIAGEM')", (telefone,))
        conn.commit()
        estado = 'TRIAGEM'
        nome = cpf = sintoma = horario = ultima_msg = None
    else:
        _, estado, nome, cpf, sintoma, horario, ultima_msg = sessao

    # =========================
    # ANTI DUPLICAÇÃO
    # =========================
    if msg == ultima_msg:
        cur.close()
        conn.close()
        return "OK", 200

    cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg, telefone))
    conn.commit()

    # =========================
    # BLOQUEIO DE ESCOPO
    # =========================
    if fora_do_escopo(msg):
        resposta = "Meu foco aqui é seu agendamento. Vamos continuar."
        enviar_whatsapp(telefone, resposta)
        cur.close()
        conn.close()
        return "OK", 200

    # =========================
    # BUSCA VAGAS
    # =========================
    cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
    vagas_lista = [v[0] for v in cur.fetchall()]
    vagas = ", ".join(vagas_lista) if vagas_lista else "Agenda cheia"

    resposta = ""

    # =========================
    # FLUXO CONTROLADO
    # =========================
    if estado == "TRIAGEM":
        sintoma = msg
        estado = "AGENDAMENTO"
        resposta = f"Entendi. Para isso, o ideal é um clínico. Tenho horários: {vagas}. Qual você escolhe?"

    elif estado == "AGENDAMENTO":
        horario_detectado = detectar_horario(msg)

        if not horario_detectado:
            resposta = f"Escolha um horário válido: {vagas}"
        else:
            horario = f"{horario_detectado}:00"
            estado = "DADOS_NOME"
            resposta = "Perfeito. Me informe seu nome completo."

    elif estado == "DADOS_NOME":
        nome = msg
        estado = "DADOS_CPF"
        resposta = "Agora preciso do seu CPF (apenas números)."

    elif estado == "DADOS_CPF":
        if not validar_cpf(msg):
            resposta = "CPF inválido. Digite os 11 números."
        else:
            cpf = msg
            estado = "CONFIRMADO"

            # baixa na agenda
            cur.execute("""
            UPDATE agenda 
            SET disponivel=FALSE 
            WHERE hora=%s AND disponivel=TRUE
            """, (horario,))

            resposta = f"Agendamento confirmado para {horario}. Nossa equipe te aguarda."

    else:
        resposta = "Meu foco aqui é seu agendamento. Vamos continuar."

    # =========================
    # ATUALIZA SESSÃO
    # =========================
    cur.execute("""
    UPDATE sessoes 
    SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s
    WHERE telefone=%s
    """, (estado, nome, cpf, sintoma, horario, telefone))

    conn.commit()
    cur.close()
    conn.close()

    # =========================
    # ENVIA RESPOSTA
    # =========================
    enviar_whatsapp(telefone, resposta)

    return "OK", 200

# =========================
# RESET
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM agenda")
    cur.execute("DELETE FROM sessoes")

    for h in ["09:00", "11:00", "14:30", "16:00"]:
        cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))

    conn.commit()
    cur.close()
    conn.close()

    return "RESET OK", 200

# =========================
# HOME
# =========================
@app.route('/')
def home():
    return "AGENTE DE ELITE BLINDADO ONLINE 🚀"

# =========================
# START
# =========================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

