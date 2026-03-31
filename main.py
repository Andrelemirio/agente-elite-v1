# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V30 — AGENTE DE ELITE (SINCRONIA PERFEITA)
# FIM DOS LOOPS E MULTI-DIAGNÓSTICO OBRIGATÓRIO
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V30 - SINCRONIA PERFEITA ATIVA")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DO CLIENTE
# =========================
NOME_CLINICA = os.environ.get("NOME_CLINICA", "Império Saúde").strip()
NOME_ATENDENTE = os.environ.get("NOME_ATENDENTE", "Ana").strip()
TIPO_CLINICA = os.environ.get("TIPO_CLINICA", "AMBOS").strip().upper()

# =========================
# CONFIGURAÇÕES DE SISTEMA
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
    conn = None
    try:
        conn = conectar(); cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                telefone TEXT PRIMARY KEY, estado TEXT, nome TEXT, 
                cpf TEXT, sintoma TEXT, horario TEXT, ultima_msg TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                id SERIAL PRIMARY KEY, hora TEXT, disponivel BOOLEAN DEFAULT TRUE
            )
        """)
        conn.commit()
    except Exception as e: print("Erro DB:", e)
    finally:
        if conn: conn.close()

init_db()

def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
    except Exception as e: print("Erro WhatsApp:", e)

# =========================
# 🧠 CÉREBRO GPT-4o (SINCRONIZADO E TOLERANTE)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, sintoma_atual, horario_atual):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    mapa_objetivos = {
        "TRIAGEM": "O paciente informará os SINTOMAS. Sua missão: 1) Nomear o especialista exato para CADA SINTOMA relatado na mesma frase. 2) Terminar perguntando se é a PRIMEIRA VEZ dele na clínica ou um retorno.",
        "STATUS_CONSULTA": "O paciente informará se é a primeira vez. Sua missão: 1) Agradecer a informação. 2) Terminar perguntando se o atendimento será PARTICULAR ou por PLANO DE SAÚDE.",
        "FORMA_PAGAMENTO": f"O paciente informará como vai pagar. Sua missão: 1) Confirmar. 2) Pedir para ele escolher UM destes horários: {vagas_txt}.",
        "AGENDAMENTO": "O paciente escolherá o horário. Sua missão: 1) Confirmar a reserva do horário. 2) Pedir o NOME COMPLETO do paciente.",
        "DADOS_NOME": "O paciente informará o nome. Sua missão: 1) Cumprimentar pelo nome. 2) Pedir os 11 números do CPF (ou avisar que pode dar na recepção).",
        "DADOS_CPF": "O paciente informará o CPF."
    }

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, Concierge de Saúde da {NOME_CLINICA}.
ESTADO DO FUNIL: {estado_atual}
O QUE VOCÊ DEVE FAZER AGORA: {mapa_objetivos.get(estado_atual)}

🛡️ REGRAS DE OURO (OBRIGATÓRIO):
1. SEJA TOLERANTE (MUITO IMPORTANTE): Se o paciente responder de forma curta ("particular", "primeira vez", "João"), aceite imediatamente! Retorne "forneceu_dado_correto": true. Não exija respostas longas ou formais.
2. MULTI-MÉDICOS: Na TRIAGEM, se ele listar 3 dores, você TEM que falar o nome dos 3 especialistas na sua resposta antes de pedir a próxima informação.
3. CONDUÇÃO PERFEITA: A última frase da sua resposta deve ser SEMPRE a pergunta que empurra o paciente para a próxima etapa, conforme a sua missão.
4. PROIBIDO: Nunca use clichês repetitivos como "Entendo", "Compreendo", "Olá!". Seja fluida e humana.

Retorne APENAS JSON:
{{
    "forneceu_dado_correto": true ou false (Seja extremamente flexível e tolerante. Use true quase sempre que ele responder o que foi pedido),
    "resposta_concierge": "O texto perfeito que será enviado ao paciente executando sua missão.",
    "dado_extraido": "O dado puro (Sintomas, Status, Pagamento, Horário, Nome ou CPF)"
}}"""

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": prompt_sistema}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except: return {"forneceu_dado_correto": False, "resposta_concierge": "Poderia repetir, por favor?", "dado_extraido": mensagem_paciente}

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
        msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else str(data.get("message", ""))
        if not telefone or not msg: return "OK", 200
        msg_clean, msg_lower = msg.strip(), msg.strip().lower()

        conn = conectar(); cur = conn.cursor()
        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        row = cur.fetchone()

        # 1. BOAS VINDAS
        if not row:
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            cur.execute("INSERT INTO sessoes (telefone, estado, ultima_msg) VALUES (%s, %s, %s)", (telefone, estado, msg_clean))
            conn.commit()
            enviar_whatsapp(telefone, f"Olá! Seja bem-vindo(a) à {NOME_CLINICA}. Sou a {NOME_ATENDENTE}. Para te direcionar corretamente, me diga: qual é o sintoma ou o tipo de consulta que você precisa?")
            return "OK", 200
        else: estado, nome, cpf, sintoma, horario, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_txt = ", ".join([v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in cur.fetchall()])

        # 2. ESCUDOS
        emergencias = ["infarto", "morrendo", "falta de ar", "sangramento", "dor forte", "socorro", "desmaiou"]
        if any(p in msg_lower for p in emergencias):
            enviar_whatsapp(telefone, "🚨 Isso pode ser uma situação de urgência. Procure imediatamente um pronto atendimento ou ligue para o SAMU (192).")
            return "OK", 200

        if any(p in msg_lower for p in ["recepção", "pessoalmente", "na hora"]) and estado == "DADOS_CPF":
            cur.execute("UPDATE agenda SET disponivel=FALSE WHERE CAST(hora AS TEXT) LIKE %s", (f"{horario}%",))
            cur.execute("UPDATE sessoes SET estado='CONFIRMADO', cpf='NA_RECEPÇÃO' WHERE telefone=%s", (telefone,))
            conn.commit()
            enviar_whatsapp(telefone, f"Perfeito! Reserva para as {horario} confirmada. Pode informar os dados na recepção. Deseja marcar para mais alguém?")
            return "OK", 200

        # 3. ANÁLISE IA
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, sintoma, horario)
        dado_limpo = str(analise.get("dado_extraido") or msg_clean)
        resposta = analise.get("resposta_concierge", "Poderia ser um pouco mais claro?")

        # 4. TRANSIÇÃO DE ESTADO SINCRONIZADA (O SEGREDO)
        # O estado só muda se a IA retornar TRUE e gerar a resposta correta.
        if analise.get("forneceu_dado_correto"):
            if estado == "TRIAGEM":
                sintoma = dado_limpo
                estado = "STATUS_CONSULTA"
            elif estado == "STATUS_CONSULTA":
                sintoma = f"{sintoma} | Status: {dado_limpo}"
                estado = "FORMA_PAGAMENTO"
            elif estado == "FORMA_PAGAMENTO":
                sintoma = f"{sintoma} | Pgto: {dado_limpo}"
                estado = "AGENDAMENTO"
            elif estado == "AGENDAMENTO":
                match = re.search(r'(\d{1,2})', dado_limpo)
                if match:
                    h_final = next((v for v in vagas_txt.split(", ") if v.startswith(match.group(1).zfill(2))), None)
                    if h_final:
                        horario = h_final
                        estado = "DADOS_NOME"
            elif estado == "DADOS_NOME":
                nome = dado_limpo
                estado = "DADOS_CPF"
            elif estado == "DADOS_CPF":
                cpf_limpo = re.sub(r'\D', '', dado_limpo)
                if len(cpf_limpo) == 11:
                    cpf = cpf_limpo
                    estado = "CONFIRMADO"
                    cur.execute("UPDATE agenda SET disponivel=FALSE WHERE CAST(hora AS TEXT) LIKE %s", (f"{horario}%",))
                    resposta = f"Tudo pronto! Seu agendamento para as {horario} está confirmado. Deseja marcar para mais alguém?"
                else:
                    estado = "DADOS_CPF"
                    resposta = "Por favor, digite os 11 números do CPF."

        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e: print("Erro:", e)
    finally:
        if conn: conn.close()
    return "OK", 200

@app.route('/reset')
def reset():
    conn = conectar(); cur = conn.cursor()
    cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
    for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
    conn.commit(); conn.close()
    return "✅ RESET V30 OK"

@app.route('/')
def home(): return "🚀 V30 ATIVA - SINCRONIA PERFEITA"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
