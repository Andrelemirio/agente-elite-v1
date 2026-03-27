Import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE DE ELITE V2.8 INICIANDO...")

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
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    conn = conectar()
    cur = conn.cursor()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS sessoes (
        telefone VARCHAR(50) PRIMARY KEY,
        estado VARCHAR(20) DEFAULT 'TRIAGEM',
        horario_escolhido TIME
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS agenda (
        id SERIAL PRIMARY KEY,
        data DATE DEFAULT CURRENT_DATE + INTERVAL '1 day',
        hora TIME,
        disponivel BOOLEAN DEFAULT TRUE,
        telefone VARCHAR(50)
    )
    ''')

    conn.commit()
    cur.close()
    conn.close()

init_db()

# =========================
# VALIDAÇÃO INTELIGENTE
# =========================
def tem_sintoma_valido(msg):
    msg = msg.lower()
    bloqueios = ["kkk", "haha", "brincadeira", "zoeira"]

    if any(b in msg for b in bloqueios):
        return False

    if len(msg.strip()) < 8:
        return False

    return True

def detectar_horario(msg):
    match = re.search(r'(\d{2}[:h]\d{2})', msg)
    return match.group(1).replace("h", ":") if match else None

# =========================
# PROMPT ELITE
# =========================
def prompt(estado, vagas):
    return f"""
Você é o Coordenador Sênior de Agendamento de uma Clínica.

MISSÃO:
Levar o paciente ao agendamento confirmado com autoridade total.

COMPORTAMENTO:
- Máximo 2 frases
- Direto, profissional, sem enrolação
- Sempre conduz a conversa
- Nunca pede desculpa
- Sempre termina com próxima ação

REGRAS:
- Só fale de saúde e agendamento
- Ignore brincadeiras
- Se fugir: "Vamos focar no seu atendimento. [pergunta]"
- Nunca peça CPF antes do nome
- Nunca aceite dados antes do sintoma

PROTOCOLOS:

SINTOMA FALSO:
"Preciso de um sintoma real para continuar. O que você está sentindo?"

DINHEIRO:
"Sua saúde vem primeiro e temos condições facilitadas. Qual seu sintoma?"

EMOCIONAL:
"Vamos focar na sua saúde física agora. O que você está sentindo?"

EMERGÊNCIA:
"ATENÇÃO: Vá ao pronto-socorro ou ligue 192 imediatamente."

ESTADO ATUAL: {estado}

HORÁRIOS DISPONÍVEIS:
{vagas if vagas else "Sem vagas disponíveis"}

FLUXO:

TRIAGEM:
Identifique sintoma real.

AGENDAMENTO:
Indique especialista + ofereça horários.

DADOS:
Peça nome → depois CPF.

FINAL:
"Agendamento pré-confirmado. Nossa equipe validará em instantes."
"""

# =========================
# MOTOR DE ESTADO
# =========================
def atualizar_estado(telefone, msg):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT estado FROM sessoes WHERE telefone=%s", (telefone,))
    row = cur.fetchone()

    estado = row[0] if row else "TRIAGEM"

    if not row:
        cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, %s)", (telefone, estado))

    if estado == "TRIAGEM" and tem_sintoma_valido(msg):
        estado = "AGENDAMENTO"

    elif estado == "AGENDAMENTO":
        horario = detectar_horario(msg)
        if horario:
            estado = "DADOS"
            cur.execute("UPDATE sessoes SET horario_escolhido=%s WHERE telefone=%s", (horario, telefone))

    cur.execute("UPDATE sessoes SET estado=%s WHERE telefone=%s", (estado, telefone))
    conn.commit()

    cur.close()
    conn.close()

    return estado

# =========================
# BAIXA NA AGENDA
# =========================
def baixar_agenda(telefone, resposta):
    if "Agendamento pré-confirmado" not in resposta:
        return

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    UPDATE agenda
    SET disponivel = FALSE, telefone=%s
    WHERE id = (
        SELECT id FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 1
    )
    """, (telefone,))

    cur.execute("DELETE FROM sessoes WHERE telefone=%s", (telefone,))

    conn.commit()
    cur.close()
    conn.close()

# =========================
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)

    if not data or data.get("fromMe"):
        return "OK", 200

    telefone = data.get("phone", "").split("@")[0]

    msg = ""
    if isinstance(data.get("text"), dict):
        msg = data["text"].get("message", "")
    else:
        msg = data.get("message", "")

    if not msg:
        return "OK", 200

    estado = atualizar_estado(telefone, msg)

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
    vagas = ", ".join([v[0].strftime('%H:%M') for v in cur.fetchall()])

    cur.close()
    conn.close()

    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": prompt(estado, vagas)},
                {"role": "user", "content": msg}
            ],
            "temperature": 0.2
        }
    )

    if res.status_code != 200:
        print(res.text)
        return "OK", 200

    resposta = res.json()['choices'][0]['message']['content']

    requests.post(
        f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
        headers={"Client-Token": ZAPI_CLIENT_TOKEN},
        json={"phone": telefone, "message": resposta}
    )

    baixar_agenda(telefone, resposta)

    return "OK", 200

# =========================
# RESET AGENDA
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")

    for h in ['08:00', '09:30', '11:00', '14:30', '16:00']:
        cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))

    conn.commit()
    cur.close()
    conn.close()

    return "RESET OK", 200

# =========================
# START
# =========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))






Olha esse codigo com prompt que o GPT gerou pra nois, me fala se vai rodar sem erros e se vai ser um agente de elite nivel 2
