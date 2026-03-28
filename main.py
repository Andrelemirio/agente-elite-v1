import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE V4.0 BLACK EDITION - ONLINE")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def inicializar_banco():
    """Garante que o banco de dados tenha as tabelas necessárias"""
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS historico_atendimento (id SERIAL PRIMARY KEY, telefone VARCHAR(50), perfil VARCHAR(20), mensagem TEXT)")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agenda_clinica (
        id SERIAL PRIMARY KEY,
        data DATE DEFAULT CURRENT_DATE + INTERVAL '1 day',
        hora TIME,
        disponivel BOOLEAN DEFAULT TRUE,
        paciente_nome TEXT,
        paciente_cpf TEXT,
        telefone_paciente VARCHAR(50)
    )
    """)
    conn.commit()
    cur.close()
    conn.close()

# Rodar a inicialização ao ligar o servidor
inicializar_banco()

# =========================
# PROMPT: O TOQUE DO CONCIERGE
# =========================
def obter_prompt_sistema(vagas):
    return f"""
Você é o Coordenador Concierge de uma Clínica Médica de Elite. 
Sua missão é organizar a saúde do paciente com autoridade e fluidez.

REGRAS DE OURO:
1. JOGO DE CINTURA: Se o paciente quiser marcar para várias pessoas ou vários exames, aceite! Diga: "Com prazer, vamos organizar todos. Primeiro, vamos garantir o horário para [SINTOMA MAIS URGENTE] e em seguida cuidamos dos demais. Qual destes horários prefere?"
2. SEM REPETIÇÃO: Nunca use a mesma frase duas vezes seguidas. Varie o vocabulário para parecer humano.
3. FOCO E SEGURANÇA: Dor no peito ou sintomas agudos têm prioridade total. Mande para o 192 se parecer grave.
4. HUMANIDADE: Se o paciente falar da família, seja acolhedor. "Cuidar da família é nossa prioridade."

VAGAS REAIS: {vagas if vagas else "Consulte disponibilidade para segunda-feira."}

COMO FINALIZAR:
Quando tiver Nome e CPF, confirme com entusiasmo:
"Tudo pronto, [NOME]! O agendamento para às [HORA] está garantido. Estaremos prontos para receber vocês!"
"""

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200
        
        telefone = data.get("phone", "").split("@")[0]
        msg = ""
        if "text" in data and isinstance(data["text"], dict):
            msg = data["text"].get("message", "")
        elif "message" in data:
            msg = data.get("message", "")
        
        if not msg: return "OK", 200

        conn = conectar_banco()
        cur = conn.cursor()

        # 1. VERIFICAR DUPLICIDADE
        cur.execute("SELECT mensagem FROM historico_atendimento WHERE telefone=%s ORDER BY id DESC LIMIT 1", (telefone,))
        ultima_msg = cur.fetchone()
        if ultima_msg and ultima_msg[0] == msg:
            return "OK", 200 

        # 2. SALVAR E BUSCAR VAGAS
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "user", msg))
        cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 4")
        vagas_lista = cur.fetchall()
        vagas = ", ".join([v[0].strftime('%H:%M') for v in vagas_lista])

        # 3. HISTÓRICO PARA IA
        cur.execute("SELECT perfil, mensagem FROM (SELECT id, perfil, mensagem FROM historico_atendimento WHERE telefone = %s ORDER BY id DESC LIMIT 8) sub ORDER BY id ASC", (telefone,))
        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas)}]
        for perfil, mensagem in cur.fetchall():
            historico_ia.append({"role": "assistant" if perfil == "assistant" else "user", "content": mensagem})

        # 4. CHAMADA OPENAI
        res = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico_ia, "temperature": 0.5})

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']
            
            # 5. SALVAR E ENVIAR
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "assistant", resposta))
            conn.commit()
            
            requests.post(f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta})

            # 6. BAIXA NA AGENDA
            if "agendamento" in resposta.lower() and "garantido" in resposta.lower():
                match = re.search(r'(\d{1,2}[:h]\d{2})', resposta)
                if match:
                    h = match.group(1).replace('h', ':')
                    cur.execute("UPDATE agenda_clinica SET disponivel=FALSE, telefone_paciente=%s WHERE hora=%s", (telefone, h))
                    conn.commit()

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
    return "OK", 200

# =========================
# ROTAS DE SUPORTE
# =========================
@app.route('/reset-agenda', methods=['GET'])
def reset():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("DELETE FROM agenda_clinica")
    for h in ['08:00', '10:00', '14:00', '16:00']:
        cur.execute("INSERT INTO agenda_clinica (hora) VALUES (%s)", (h,))
    conn.commit()
    cur.close()
    conn.close()
    return "✅ AGENDA BLACK EDITION RESETADA", 200

@app.route('/', methods=['GET'])
def home():
    return "AGENTE BLACK EDITION OPERACIONAL 🚀", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
