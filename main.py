import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE V3.9 SÊNIOR HUMANIZADO - ONLINE")

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

inicializar_banco()

# =========================
# PROMPT SÊNIOR HUMANIZADO
# =========================
def obter_prompt_sistema(vagas):
    return f"""
Você é o Coordenador Sênior de uma Clínica Médica de Alto Padrão. Sua postura é de extrema autoridade, empatia e foco em conversão.

REGRAS DE OURO:
1. FOCO NO AGORA: Ignore sintomas mencionados em conversas antigas se o paciente trouxer algo novo hoje.
2. NÃO É MÉDICO: Nunca dê diagnósticos. Se o paciente insistir, diga: "Entendo sua preocupação, mas somente o médico pode avaliar isso com precisão. Vamos garantir sua vaga para que ele te ajude?"
3. EMERGÊNCIA: Se o paciente falar em morte, suicídio ou dor insuportável, seja humano primeiro: "Sinto muito que esteja passando por isso, sua vida é prioridade." Depois, oriente buscar o 192 ou pronto-socorro IMEDIATAMENTE.
4. ESTILO: Polido, direto e resolutivo. Máximo 3 frases.

VAGAS DISPONÍVEIS:
{vagas if vagas else "Consulte a disponibilidade para amanhã."}

FLUXO:
- Valide o sintoma atual.
- Ofereça os horários acima.
- Após o horário escolhido, peça Nome e CPF.
- AO FINALIZAR, diga: "Perfeito! Seu agendamento para às [HORA ESCOLHIDA] foi realizado com sucesso. Nossa equipe de elite te aguarda!" 
(Substitua [HORA ESCOLHIDA] pelo horário que você e o paciente combinaram).
"""

# =========================
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.get_json(force=True)
    except: return "OK", 200

    if not dados or dados.get("fromMe"): return "OK", 200

    telefone = dados.get("phone", "").split("@")[0]
    msg = dados.get("text", {}).get("message", "") if isinstance(dados.get("text"), dict) else data.get("message", "")
    if not telefone or not msg: return "OK", 200

    conn = None
    try:
        conn = conectar_banco()
        cur = conn.cursor()

        # Salvar msg do cliente
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "user", msg))
        conn.commit()

        # Buscar vagas
        cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 4")
        vagas_lista = cur.fetchall()
        vagas = ", ".join([v[0].strftime('%H:%M') for v in vagas_lista])

        # Histórico (Contexto)
        cur.execute("SELECT perfil, mensagem FROM (SELECT id, perfil, mensagem FROM historico_atendimento WHERE telefone = %s ORDER BY id DESC LIMIT 10) sub ORDER BY id ASC", (telefone,))
        
        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas)}]
        for perfil, mensagem in cur.fetchall():
            role = "assistant" if perfil == "assistant" else "user"
            historico_ia.append({"role": role, "content": mensagem})

        # IA
        res = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico_ia, "temperature": 0.4})

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']

            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "assistant", resposta))
            conn.commit()

            requests.post(f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta})

            # Baixa na agenda
            if "agendamento realizado com sucesso" in resposta.lower():
                horario_match = re.search(r'(\d{1,2}[:h]\d{2})', resposta)
                if horario_match:
                    h_conf = horario_match.group(1).replace('h', ':')
                    cur.execute("UPDATE agenda_clinica SET disponivel = FALSE, telefone_paciente = %s WHERE hora = %s", (telefone, h_conf))
                conn.commit()

    except Exception as e: print(f"Erro: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
    return "OK", 200

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
    return "Agenda Resetada!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
