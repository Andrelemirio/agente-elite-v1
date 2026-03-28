import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE V6.0 SÊNIOR HUMANIZADO - ONLINE")

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURAÇÕES DE AMBIENTE
# ==========================================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ==========================================
# 🗄️ GESTÃO DE BANCO DE DADOS
# ==========================================
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def inicializar_banco():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historico_atendimento (
            id SERIAL PRIMARY KEY, 
            telefone VARCHAR(50), 
            perfil VARCHAR(20), 
            mensagem TEXT
        )
    """)
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

inicializar_banco()

# ==========================================
# 🧠 O CÉREBRO (PROMPT V6.0 - EMPATIA E EXCELÊNCIA OMNICHANNEL)
# ==========================================
def obter_prompt_sistema(vagas):
    return f"""
Você é o Concierge Sênior de uma clínica médica de altíssimo padrão. Sua postura une Acolhimento Humanizado, Empatia, Comunicação Clara e Gestão Eficiente. Você conduz o paciente com segurança e cuidado.

REGRA MÁXIMA (O FUNIL SNIPER): Você faz APENAS UMA (1) pergunta por mensagem. NUNCA pule etapas ou peça vários dados de uma vez.

AS 4 ETAPAS DO ATENDIMENTO DE EXCELÊNCIA:
1. ACOLHIMENTO: Se não sabe o nome da pessoa, recepcione com empatia e pergunte o primeiro nome e como pode ajudar hoje. (ESPERE A RESPOSTA)
2. TRIAGEM EMPÁTICA: Sabendo o nome, acolha a dor/preocupação do paciente com humanidade (ex: "Compreendo como isso é desconfortável", "A saúde da sua família é nossa prioridade") e pergunte APENAS qual o sintoma exato. (ESPERE A RESPOSTA)
3. PROATIVIDADE NA AGENDA: Sabendo o sintoma, ofereça as opções de horários com clareza e pergunte APENAS qual ele prefere. (ESPERE A RESPOSTA)
4. GESTÃO E FECHAMENTO: SOMENTE após ele escolher o horário, peça o Nome Completo e o CPF para garantir a vaga no sistema.

DIRETRIZES DO SÊNIOR:
- NUNCA dê diagnósticos. Você é o gestor do atendimento, não o médico.
- SEJA CLARO E ÁGIL: Responda de forma acolhedora, mas em no máximo 3 linhas.
- EMERGÊNCIA REAL (Dores no peito, risco de vida): Mostre empatia extrema, mas seja firme: "Sua vida é nossa prioridade absoluta. Por segurança, vá imediatamente ao pronto-socorro mais próximo ou ligue 192."

VAGAS REAIS PARA HOJE/AMANHÃ: {vagas if vagas else "Nossa agenda está completa hoje, mas posso verificar um encaixe ou lista de espera prioritária para você."}

FINALIZAÇÃO:
Quando receber o CPF (Passo 4), encerre o atendimento com excelência: "Perfeito! Sua reserva para às [HORA] está confirmada. Cuidaremos muito bem de você aqui na clínica."
"""

# ==========================================
# 📡 WEBHOOK PRINCIPAL (O MOTOR)
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200
        
        telefone = data.get("phone", "").split("@")[0]
        msg = data.get("text", {}).get("message", "") if "text" in data and isinstance(data["text"], dict) else data.get("message", "")
        if not msg: return "OK", 200

        conn = conectar_banco()
        cur = conn.cursor()

        cur.execute("SELECT mensagem FROM historico_atendimento WHERE telefone=%s ORDER BY id DESC LIMIT 1", (telefone,))
        ultima = cur.fetchone()
        if ultima and ultima[0] == msg: return "OK", 200

        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "user", msg))
        conn.commit()

        cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 5")
        vagas_db = cur.fetchall()
        vagas_formatadas = ", ".join([v[0].strftime('%H:%M') for v in vagas_db])

        cur.execute("""
            SELECT perfil, mensagem FROM (
                SELECT id, perfil, mensagem FROM historico_atendimento 
                WHERE telefone = %s ORDER BY id DESC LIMIT 15
            ) sub ORDER BY id ASC
        """, (telefone,))
        
        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas_formatadas)}]
        for perfil, mensagem in cur.fetchall():
            historico_ia.append({"role": "assistant" if perfil == "assistant" else "user", "content": mensagem})

        # Temperatura 0.5: Equilíbrio perfeito entre seguir as regras (Sniper) e soar humano (Empatia)
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico_ia, "temperature": 0.5}
        )

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']
            
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "assistant", resposta))
            conn.commit()
            
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta}
            )

            if "reserva para às" in resposta.lower() and "confirmada" in resposta.lower():
                match = re.search(r'(\d{1,2}[:h]\d{2})', resposta)
                if match:
                    h_extraida = match.group(1).replace('h', ':')
                    cur.execute("UPDATE agenda_clinica SET disponivel=FALSE, telefone_paciente=%s WHERE hora=%s", (telefone, h_extraida))
                    conn.commit()

    except Exception as e:
        print(f"❌ ERRO NO MOTOR: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
    return "OK", 200

# ==========================================
# 🛠️ UTILITÁRIOS
# ==========================================
@app.route('/reset-agenda', methods=['GET'])
def reset():
    try:
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("DELETE FROM agenda_clinica")
        horarios = ['08:00', '09:30', '11:00', '14:30', '16:00', '17:30']
        for h in horarios:
            cur.execute("INSERT INTO agenda_clinica (hora) VALUES (%s)", (h,))
        conn.commit()
        cur.close()
        conn.close()
        return "✅ AGENDA V6.0 SÊNIOR RESETADA COM SUCESSO!", 200
    except Exception as e:
        return f"Erro ao resetar: {e}", 500

@app.route('/', methods=['GET'])
def home():
    return "🚀 IMPÉRIO DE SILÍCIO V6.0 SÊNIOR HUMANIZADO - ONLINE", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
