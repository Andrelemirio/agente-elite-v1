import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE V5.2 SNIPER - ONLINE")

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
# 🧠 O CÉREBRO (PROMPT SNIPER - 1 PERGUNTA POR VEZ)
# ==========================================
def obter_prompt_sistema(vagas):
    return f"""
Você é o Gerente Sênior de Triagem de uma clínica médica de altíssimo padrão. Você é direto, autoritário e conduz a conversa com pulso firme.

REGRA DE OURO MÁXIMA: VOCÊ SÓ PODE FAZER UMA (1) PERGUNTA POR MENSAGEM. NUNCA JUNTE DUAS ETAPAS. É ESTRITAMENTE PROIBIDO PEDIR SINTOMA E CPF NA MESMA MENSAGEM.

O FUNIL DE VENDAS (Execute APENAS UM passo por vez e aguarde a resposta do paciente):
PASSO 1: Se não sabe o primeiro nome de quem está falando, pergunte apenas o nome. (PARE E ESPERE A RESPOSTA)
PASSO 2: Sabendo o nome, pergunte APENAS qual o sintoma ou dor do paciente. (PARE E ESPERE A RESPOSTA)
PASSO 3: Sabendo o sintoma, ofereça as vagas abaixo e pergunte APENAS qual horário prefere. (PARE E ESPERE A RESPOSTA)
PASSO 4: SOMENTE APÓS o paciente escolher o horário exato, exija o Nome Completo e o CPF para o bloqueio da vaga.

PROIBIÇÕES ABSOLUTAS:
- NUNCA diga "Claro, estou aqui para ajudar", "Compreendo", "Sinto muito", "Peço desculpas".
- NUNCA peça CPF ou Nome Completo antes do PASSO 4.
- Responda com no máximo 2 linhas. Seja curto e cirúrgico.
- Ignore histórias pessoais, reclamações ou piadas. Foque exclusivamente no agendamento.
- Para situações de risco à vida (ex: enfarte, suicídio), diga APENAS: "Para risco à vida, acione o 192 ou vá ao pronto-socorro imediatamente."

VAGAS REAIS PARA HOJE/AMANHÃ: {vagas if vagas else "Sem vagas no momento."}

FINALIZAÇÃO:
Quando o paciente enviar o CPF no Passo 4, encerre dizendo EXATAMENTE: "Reserva confirmada para às [HORA]. Nossa equipe aguarda o paciente."
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

        # 1. BLOQUEIO DE DUPLICIDADE
        cur.execute("SELECT mensagem FROM historico_atendimento WHERE telefone=%s ORDER BY id DESC LIMIT 1", (telefone,))
        ultima = cur.fetchone()
        if ultima and ultima[0] == msg: return "OK", 200

        # 2. SALVAR MENSAGEM DO USUÁRIO
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "user", msg))
        conn.commit()

        # 3. BUSCAR VAGAS
        cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 5")
        vagas_db = cur.fetchall()
        vagas_formatadas = ", ".join([v[0].strftime('%H:%M') for v in vagas_db])

        # 4. MEMÓRIA BLINDADA (15 mensagens)
        cur.execute("""
            SELECT perfil, mensagem FROM (
                SELECT id, perfil, mensagem FROM historico_atendimento 
                WHERE telefone = %s ORDER BY id DESC LIMIT 15
            ) sub ORDER BY id ASC
        """, (telefone,))
        
        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas_formatadas)}]
        for perfil, mensagem in cur.fetchall():
            historico_ia.append({"role": "assistant" if perfil == "assistant" else "user", "content": mensagem})

        # 5. OPENAI (Temperatura baixa 0.4 para focar na obediência do funil)
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico_ia, "temperature": 0.4}
        )

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']
            
            # 6. SALVAR E ENVIAR
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "assistant", resposta))
            conn.commit()
            
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta}
            )

            # 7. BAIXA INTELIGENTE
            if "reserva confirmada" in resposta.lower():
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
        return "✅ AGENDA SNIPER RESETADA COM SUCESSO!", 200
    except Exception as e:
        return f"Erro ao resetar: {e}", 500

@app.route('/', methods=['GET'])
def home():
    return "🚀 IMPÉRIO DE SILÍCIO V5.2 SNIPER - ONLINE", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
