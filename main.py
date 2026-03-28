import os
import requests
import psycopg2
from flask import Flask, request

print("🚀 AGENTE DE ELITE FINAL - ONLINE")

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

# =========================
# PROMPT SÊNIOR (CÉREBRO)
# =========================
def obter_prompt_sistema(vagas):
    return f"""
Você é um atendente sênior de clínica médica com mais de 10 anos de experiência.

Seu objetivo é conduzir o paciente até o agendamento de forma natural e profissional.

COMPORTAMENTO:
- Fale como humano
- Seja educado, direto e claro
- Demonstre empatia quando necessário
- Não seja robótico
- Não repita perguntas

FLUXO:
1. Entenda o que o paciente sente
2. Se ele não souber explicar, ajude com perguntas simples
3. Sugira o especialista
4. Ofereça horários reais
5. Conduza para agendamento
6. Após escolha do horário, peça nome e CPF

REGRAS:
- Nunca ignore o que o paciente disse
- Nunca repita a mesma pergunta
- Se for brincadeira, traga para o foco com leveza
- Se estiver confuso, ajude ele

HORÁRIOS DISPONÍVEIS:
{vagas if vagas else "Sem horários no momento, posso verificar novas vagas para você."}

FINALIZAÇÃO:
Quando tiver nome e CPF:
"Perfeito, agendamento realizado com sucesso. Nossa equipe te aguarda!"

Seja natural e resolutivo.
"""

# =========================
# WEBHOOK
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

        # SALVAR MSG CLIENTE
        cur.execute("""
        INSERT INTO historico_atendimento (telefone, perfil, mensagem)
        VALUES (%s, %s, %s)
        """, (telefone, "user", msg))
        conn.commit()

        # BUSCAR VAGAS
        cur.execute("""
        SELECT hora FROM agenda_clinica
        WHERE disponivel = TRUE
        ORDER BY hora ASC LIMIT 4
        """)
        vagas_lista = cur.fetchall()
        vagas = ", ".join([v[0].strftime('%H:%M') for v in vagas_lista]) if vagas_lista else ""

        # HISTÓRICO
        cur.execute("""
        SELECT perfil, mensagem FROM historico_atendimento
        WHERE telefone = %s
        ORDER BY id DESC LIMIT 10
        """, (telefone,))

        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas)}]

        for perfil, mensagem in reversed(cur.fetchall()):
            role = "assistant" if perfil == "assistant" else "user"
            historico_ia.append({"role": role, "content": mensagem})

        # OPENAI
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": historico_ia,
                "temperature": 0.4
            }
        )

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']

            # SALVAR RESPOSTA
            cur.execute("""
            INSERT INTO historico_atendimento (telefone, perfil, mensagem)
            VALUES (%s, %s, %s)
            """, (telefone, "assistant", resposta))
            conn.commit()

            # ENVIAR WHATSAPP
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta}
            )

            # MARCAR AGENDA (quando finalizar)
            if "agendamento realizado com sucesso" in resposta.lower():
                cur.execute("""
                UPDATE agenda_clinica
                SET disponivel = FALSE, telefone_paciente = %s
                WHERE id = (
                    SELECT id FROM agenda_clinica
                    WHERE disponivel = TRUE
                    ORDER BY hora ASC LIMIT 1
                )
                """, (telefone,))
                conn.commit()

    except Exception as e:
        print(f"ERRO: {e}")

    finally:
        if conn:
            cur.close()
            conn.close()

    return "OK", 200

# =========================
# RESET AGENDA
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

    return "Agenda resetada", 200

# =========================
# HOME
# =========================
@app.route('/', methods=['GET'])
def home():
    return "AGENTE DE ELITE ONLINE 🚀", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))




