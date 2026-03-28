import os
import requests
import psycopg2
import re  # Para extração inteligente de horários
from flask import Flask, request
from datetime import datetime

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE V3.8 SÊNIOR BLINDADO - ONLINE")

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

# =========================
# BANCO DE DADOS
# =========================
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def inicializar_banco():
    conn = conectar_banco()
    cur = conn.cursor()
    # Histórico
    cur.execute("CREATE TABLE IF NOT EXISTS historico_atendimento (id SERIAL PRIMARY KEY, telefone VARCHAR(50), perfil VARCHAR(20), mensagem TEXT)")
    # Agenda Profissional
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

# =========================
# PROMPT SÊNIOR CONCIERGE
# =========================
def obter_prompt_sistema(vagas):
    return f"""
Você é o Coordenador Sênior de Atendimento de uma Clínica Médica de Alto Padrão, com 10 anos de experiência.

SUA MISSÃO: 
Converter o contato em agendamento com excelência, autoridade e humanização.

DIRETRIZES DE ÉTICA E SEGURANÇA (LEGAL):
- Você NÃO é médico. Nunca dê diagnósticos, não prescreva e não afirme doenças.
- Se o paciente perguntar "o que eu tenho?", responda: "Apenas o médico pode realizar essa avaliação com precisão. Meu papel é garantir que você seja atendido pelo especialista correto."
- Sua prioridade é a saúde física do paciente.

ESTILO DE COMUNICAÇÃO:
- Polido, empático, resolutivo e direto. Máximo 3 frases.
- Trate o paciente com exclusividade. Não repita perguntas.

FLUXO DE CONVERSÃO:
1. Valide o sintoma com atenção.
2. Sugira o especialista ideal para o caso.
3. Ofereça as vagas reais abaixo.
4. Após o horário escolhido, solicite Nome e CPF para blindar a reserva.

VAGAS DISPONÍVEIS AGORA:
{vagas if vagas else "Estamos com a agenda lotada, mas posso verificar uma desistência para você."}

CONFIRMAÇÃO FINAL:
Quando receber Nome e CPF, diga exatamente: 
"Perfeito! Seu agendamento para às [HORÁRIO] foi realizado com sucesso. Nossa equipe de elite te aguarda!"
"""

# =========================
# WEBHOOK (O MOTOR)
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.get_json(force=True)
    except:
        return "OK", 200

    if not dados or dados.get("fromMe"):
        return "OK", 200

    telefone = dados.get("phone", "").split("@")[0]
    msg = dados.get("text", {}).get("message", "") if isinstance(dados.get("text"), dict) else dados.get("message", "")

    if not telefone or not msg:
        return "OK", 200

    conn = None
    try:
        conn = conectar_banco()
        cur = conn.cursor()

        # 1. SALVAR MENSAGEM DO CLIENTE
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "user", msg))
        conn.commit()

        # 2. BUSCAR VAGAS REAIS
        cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 4")
        vagas_lista = cur.fetchall()
        vagas = ", ".join([v[0].strftime('%H:%M') for v in vagas_lista])

        # 3. CONSTRUIR HISTÓRICO PARA IA
        cur.execute("SELECT perfil, mensagem FROM (SELECT id, perfil, mensagem FROM historico_atendimento WHERE telefone = %s ORDER BY id DESC LIMIT 10) sub ORDER BY id ASC", (telefone,))
        
        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas)}]
        for perfil, mensagem in cur.fetchall():
            role = "assistant" if perfil == "assistant" else "user"
            historico_ia.append({"role": role, "content": mensagem})

        # 4. CHAMADA OPENAI
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico_ia, "temperature": 0.4}
        )

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']

            # 5. SALVAR RESPOSTA DA IA
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "assistant", resposta))
            conn.commit()

            # 6. ENVIAR VIA Z-API
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta}
            )

            # 7. LOGICA DE RESERVA PRECISA (DANDO BAIXA NO HORÁRIO CORRETO)
            if "agendamento realizado com sucesso" in resposta.lower():
                # Tenta extrair o horário que a IA confirmou na resposta
                horario_match = re.search(r'(\d{2}[:h]\d{2})', resposta)
                if horario_match:
                    horario_confirmado = horario_match.group(1).replace('h', ':')
                    cur.execute("""
                        UPDATE agenda_clinica 
                        SET disponivel = FALSE, telefone_paciente = %s 
                        WHERE hora = %s AND disponivel = TRUE
                    """, (telefone, horario_confirmado))
                else:
                    # Fallback caso a Regex falhe: pega o primeiro disponível
                    cur.execute("UPDATE agenda_clinica SET disponivel = FALSE, telefone_paciente = %s WHERE id = (SELECT id FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 1)", (telefone,))
                
                conn.commit()

    except Exception as e:
        print(f"🔥 ERRO OPERACIONAL: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

    return "OK", 200

# =========================
# FERRAMENTAS ADMIN
# =========================
@app.route('/reset-agenda', methods=['GET'])
def reset():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("DELETE FROM agenda_clinica")
    for h in ['08:00', '09:30', '11:00', '14:30', '16:00']:
        cur.execute("INSERT INTO agenda_clinica (hora) VALUES (%s)", (h,))
    conn.commit()
    cur.close()
    conn.close()
    return "✅ AGENDA RESETADA PARA PADRÃO SÊNIOR", 200

@app.route('/', methods=['GET'])
def home():
    return "SISTEMA DE ELITE ONLINE 🚀", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

