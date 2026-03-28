Import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE DE ELITE CONTROLADO - FINAL ATIVO")

app = Flask(__name__)

# =========================
# CONFIG
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# BANCO
# =========================
def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessoes (
        telefone TEXT PRIMARY KEY,
        estado TEXT,
        nome TEXT,
        cpf TEXT,
        horario TEXT
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
# UTIL
# =========================
def enviar(telefone, msg):
    requests.post(
        f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
        headers={"Client-Token": ZAPI_CLIENT_TOKEN},
        json={"phone": telefone, "message": msg}
    )

def detectar_emergencia(msg):
    gatilhos = ["me matar", "suicidio", "vou pular", "quero morrer"]
    return any(p in msg.lower() for p in gatilhos)

def detectar_fora_escopo(msg):
    gatilhos = ["dinheiro", "pix", "emprestado"]
    return any(p in msg.lower() for p in gatilhos)

def extrair_horario(msg):
    match = re.search(r'\d{2}:\d{2}', msg)
    return match.group() if match else None

def cpf_valido(cpf):
    return bool(re.fullmatch(r'\d{11}', cpf))

# =========================
# PROMPT (IA AUXILIAR)
# =========================
def gerar_resposta_ia(msg):
    prompt = f"""
Você é um atendente sênior de clínica.

Responda com:
- Empatia
- Clareza
- Objetividade

Mensagem do paciente:
{msg}
"""

    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5
        }
    )

    return res.json()['choices'][0]['message']['content']

# =========================
# FLUXO CONTROLADO
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)

    if not data or data.get("fromMe"):
        return "OK", 200

    telefone = data.get("phone", "").split("@")[0]
    msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else data.get("message", "")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT estado, nome, cpf, horario FROM sessoes WHERE telefone=%s", (telefone,))
    row = cur.fetchone()

    if not row:
        cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s,'INICIO')", (telefone,))
        conn.commit()
        estado, nome, cpf, horario = "INICIO", None, None, None
    else:
        estado, nome, cpf, horario = row

    # =========================
    # BLOQUEIOS CRÍTICOS
    # =========================
    if detectar_emergencia(msg):
        enviar(telefone, "Sua vida é importante. Ligue 188 agora (CVV). Atendimento 24h.")
        return "OK", 200

    if detectar_fora_escopo(msg):
        enviar(telefone, "Posso te ajudar com agendamentos médicos. Vamos focar nisso.")
        return "OK", 200

    # =========================
    # FLUXO PRINCIPAL
    # =========================
    if estado == "INICIO":
        enviar(telefone, "Me diga o que você está sentindo para eu te direcionar corretamente.")
        novo_estado = "SINTOMA"

    elif estado == "SINTOMA":
        especialidade = "clínico geral"
        if "estomago" in msg.lower():
            especialidade = "gastroenterologista"
        elif "olho" in msg.lower():
            especialidade = "oftalmologista"

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE LIMIT 3")
        horarios = [h[0] for h in cur.fetchall()]
        texto = ", ".join(horarios) if horarios else "Sem horários disponíveis"

        enviar(telefone, f"Para seu caso, o ideal é {especialidade}. Tenho: {texto}. Qual horário você escolhe?")
        novo_estado = "HORARIO"

    elif estado == "HORARIO":
        h = extrair_horario(msg)

        if not h:
            enviar(telefone, "Escolha um horário válido no formato 14:30.")
            return "OK", 200

        cur.execute("UPDATE sessoes SET horario=%s WHERE telefone=%s", (h, telefone))
        enviar(telefone, "Perfeito. Me informe seu nome completo.")
        novo_estado = "NOME"

    elif estado == "NOME":
        cur.execute("UPDATE sessoes SET nome=%s WHERE telefone=%s", (msg, telefone))
        enviar(telefone, "Agora preciso do seu CPF (11 dígitos).")
        novo_estado = "CPF"

    elif estado == "CPF":
        if not cpf_valido(msg):
            enviar(telefone, "CPF inválido. Envie os 11 números.")
            return "OK", 200

        cur.execute("UPDATE sessoes SET cpf=%s WHERE telefone=%s", (msg, telefone))

        # CONFIRMAÇÃO REAL
        cur.execute("UPDATE agenda SET disponivel=FALSE WHERE hora=%s AND disponivel=TRUE LIMIT 1", (horario,))
        enviar(telefone, "Agendamento confirmado. Nossa equipe te aguarda.")
        cur.execute("DELETE FROM sessoes WHERE telefone=%s", (telefone,))
        novo_estado = None

    else:
        resposta = gerar_resposta_ia(msg)
        enviar(telefone, resposta)
        return "OK", 200

    if novo_estado:
        cur.execute("UPDATE sessoes SET estado=%s WHERE telefone=%s", (novo_estado, telefone))

    conn.commit()
    cur.close()
    conn.close()

    return "OK", 200

# =========================
# RESET
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM agenda")
    for h in ["09:00","11:00","14:30","16:00"]:
        cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))

    conn.commit()
    cur.close()
    conn.close()

    return "Agenda resetada", 200

@app.route('/')
def home():
    return "AGENTE ELITE CONTROLADO ONLINE", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
