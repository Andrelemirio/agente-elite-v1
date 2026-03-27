import os  # Corrigido: 'i' minúsculo para não dar erro no Render
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE DE ELITE V2.8.5 - NÍVEL 2 SÊNIOR ATIVADO!")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DE AMBIENTE
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# BANCO DE DADOS
# =========================
def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    conn = conectar()
    cur = conn.cursor()
    # Tabela de Estados (Cérebro do fluxo)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS sessoes (
        telefone VARCHAR(50) PRIMARY KEY,
        estado VARCHAR(20) DEFAULT 'TRIAGEM',
        horario_escolhido TIME
    )
    ''')
    # Tabela de Agenda (Estoque da clínica)
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
# LÓGICA DE INTELIGÊNCIA
# =========================
def detectar_horario(msg):
    # Procura padrões como 10:00 ou 10h00
    match = re.search(r'(\d{2}[:h]\d{2})', msg)
    return match.group(1).replace("h", ":") if match else None

def atualizar_estado(telefone, msg):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM sessoes WHERE telefone=%s", (telefone,))
    row = cur.fetchone()
    estado = row[0] if row else "TRIAGEM"

    if not row:
        cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, 'TRIAGEM')", (telefone,))
    
    msg_limpa = msg.lower()
    
    # Transição: TRIAGEM -> AGENDAMENTO (Se descreveu sintoma real)
    if estado == "TRIAGEM" and len(msg_limpa) > 8 and "kkk" not in msg_limpa:
        estado = "AGENDAMENTO"
    
    # Transição: AGENDAMENTO -> DADOS (Se escolheu um horário)
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

def baixar_agenda(telefone, resposta):
    # Só executa se a IA confirmou o final
    if "Agendamento pré-confirmado" not in resposta:
        return

    conn = conectar()
    cur = conn.cursor()
    
    # Puxa o horário que o cliente ESCOLHEU na sessão
    cur.execute("SELECT horario_escolhido FROM sessoes WHERE telefone=%s", (telefone,))
    res_sessao = cur.fetchone()
    
    if res_sessao and res_sessao[0]:
        horario = res_sessao[0]
        # Dá baixa exatamente no horário que o cliente escolheu
        cur.execute("""
        UPDATE agenda
        SET disponivel = FALSE, telefone=%s
        WHERE hora = %s AND disponivel = TRUE
        """, (telefone, horario))
        
        # Limpa a sessão para um futuro novo atendimento
        cur.execute("DELETE FROM sessoes WHERE telefone=%s", (telefone,))
        conn.commit()
        print(f"✅ SUCESSO: Horário {horario} reservado para {telefone}")

    cur.close()
    conn.close()

# =========================
# PROMPT SÊNIOR DE ELITE
# =========================
def gerar_prompt(estado, vagas):
    return f"""
Você é o Coordenador Sênior de Agendamento da Clínica. Sua voz é de autoridade, seca e profissional.

DIRETRIZES:
- Máximo 2 frases por resposta.
- Nunca peça desculpas. Nunca use 'por favor'.
- Se o cliente brincar ou fugir do assunto, corte: "Vamos focar no seu atendimento. Qual seu sintoma?"

ESTADO ATUAL DA CONVERSA: {estado}

VAGAS REAIS NO SISTEMA:
{vagas if vagas else "Agenda lotada no momento."}

PROTOCOLO POR ESTADO:
1. TRIAGEM: Extraia o sintoma físico real. Não sugira médico nem horário agora.
2. AGENDAMENTO: Indique o especialista correto e ofereça APENAS as vagas acima. O cliente deve escolher uma.
3. DADOS: Horário aceito. Peça Nome Completo e depois o CPF.
4. FINAL: Somente após o CPF, diga exatamente: "Agendamento pré-confirmado. Nossa equipe validará em instantes."
"""

# =========================
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    if not data or data.get("fromMe"): return "OK", 200

    telefone = data.get("phone", "").split("@")[0]
    msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else data.get("message", "")
    
    if not msg: return "OK", 200

    # 1. Atualiza cérebro do fluxo
    estado = atualizar_estado(telefone, msg)

    # 2. Busca horários livres
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora ASC LIMIT 4")
    vagas = ", ".join([v[0].strftime('%H:%M') for v in cur.fetchall()])
    cur.close()
    conn.close()

    # 3. Chama Inteligência
    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": gerar_prompt(estado, vagas)},
                {"role": "user", "content": msg}
            ],
            "temperature": 0.2
        }
    )

    if res.status_code == 200:
        resposta = res.json()['choices'][0]['message']['content']
        
        # Envia via Z-API
        requests.post(
            f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
            json={"phone": telefone, "message": resposta}
        )

        # 4. Tenta dar baixa na agenda
        baixar_agenda(telefone, resposta)

    return "OK", 200

# =========================
# RESET E ADMIN
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
    return "✅ SISTEMA RESETADO E AGENDA PRONTA!", 200

@app.route('/', methods=['GET'])
def home():
    return "AGENTE DE ELITE V2.8.5 ONLINE 🚀", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
