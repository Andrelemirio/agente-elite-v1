import os  # Corrigido
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE DE ELITE V3.1 - SÊNIOR BLINDADO ATIVADO!")

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

def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    conn = conectar()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS sessoes (telefone VARCHAR(50) PRIMARY KEY, estado VARCHAR(20) DEFAULT 'TRIAGEM', horario_escolhido TIME)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS agenda (id SERIAL PRIMARY KEY, hora TIME, disponivel BOOLEAN DEFAULT TRUE, telefone VARCHAR(50))''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

# =========================
# INTELIGÊNCIA DE FLUXO
# =========================
def detectar_horario(msg):
    # Pega 9:00, 09:00, 14h30, etc.
    match = re.search(r'(\d{1,2}[:h]\d{2})', msg.lower())
    return match.group(1).replace("h", ":") if match else None

def atualizar_estado(telefone, msg):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM sessoes WHERE telefone=%s", (telefone,))
    row = cur.fetchone()
    estado = row[0] if row else "TRIAGEM"

    if not row:
        cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, 'TRIAGEM')", (telefone,))
    
    msg_limpa = msg.lower().strip()
    
    # Lógica Inteligente de Transição
    if estado == "TRIAGEM":
        # Se não for só um "oi" e tiver conteúdo, avança.
        if len(msg_limpa) > 3 and msg_limpa not in ["ola", "oi", "bom dia", "boa tarde"]:
            estado = "AGENDAMENTO"
            
    elif estado == "AGENDAMENTO":
        horario = detectar_horario(msg_limpa)
        if horario:
            estado = "DADOS"
            cur.execute("UPDATE sessoes SET horario_escolhido=%s WHERE telefone=%s", (horario, telefone))

    cur.execute("UPDATE sessoes SET estado=%s WHERE telefone=%s", (estado, telefone))
    conn.commit()
    cur.close()
    conn.close()
    return estado

# =========================
# PROMPT SÊNIOR (FIM DO LOOP)
# =========================
def prompt_sistema(estado, vagas):
    vagas_texto = vagas if vagas else "08:00, 09:30, 11:00, 14:00"
    return f"""
Você é o Coordenador Sênior da Clínica. Direto, autoridade, máximo 2 frases.

ESTADO ATUAL: {estado}
VAGAS DISPONÍVEIS: {vagas_texto}

REGRAS:
1. Se o cliente disser QUALQUER incômodo (ex: 'cabeça', 'olho ruim'), aceite como sintoma. 
2. Valide o sintoma, sugira o especialista e ofereça os horários acima IMEDIATAMENTE.
3. Se o cliente estiver confuso, sugira: "Pelo que disse, recomendo um Clínico Geral. Tenho 09:30 ou 11:00. Qual prefere?"
4. Não repita "Qual seu sintoma" se ele já falou uma dor. Avance para o agendamento.
5. Ao final (CPF recebido), diga: "Agendamento pré-confirmado. Nossa equipe validará em instantes."
"""

# =========================
# WEBHOOK E BAIXA
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    if not data or data.get("fromMe"): return "OK", 200
    telefone = data.get("phone", "").split("@")[0]
    msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else data.get("message", "")
    if not msg: return "OK", 200

    estado = atualizar_estado(telefone, msg)

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora ASC LIMIT 4")
    vagas = ", ".join([v[0].strftime('%H:%M') for v in cur.fetchall()])
    cur.close()
    conn.close()

    res = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "system", "content": prompt_sistema(estado, vagas)}, {"role": "user", "content": msg}],
            "temperature": 0.2
        }
    )

    if res.status_code == 200:
        resposta = res.json()['choices'][0]['message']['content']
        requests.post(f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
            json={"phone": telefone, "message": resposta})
        
        if "Agendamento pré-confirmado" in resposta:
            # Lógica de baixa simplificada para o teste
            conn = conectar()
            cur = conn.cursor()
            cur.execute("UPDATE agenda SET disponivel=FALSE, telefone=%s WHERE disponivel=TRUE LIMIT 1", (telefone,))
            cur.execute("DELETE FROM sessoes WHERE telefone=%s", (telefone,))
            conn.commit()
            cur.close()
            conn.close()

    return "OK", 200

@app.route('/reset', methods=['GET'])
def reset():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
    for h in ['08:00', '10:00', '14:00', '16:00']:
        cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
    conn.commit()
    cur.close()
    conn.close()
    return "RESET OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
