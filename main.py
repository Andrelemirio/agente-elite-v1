# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V26 — AGENTE DE ELITE (FINAL DE MERCADO)
# FAST MAPPING + TRIAGEM LOGÍSTICA + FECHAMENTO RÁPIDO
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V26 - VERSÃO FINAL ATIVA")

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
# 🧠 CÉREBRO GPT-4o (FAST MAPPING DE ELITE)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, sintoma_atual, horario_atual):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    mapa_objetivos = {
        "TRIAGEM": "Identificar o sintoma e mapear IMEDIATAMENTE para o especialista correto. Se o paciente for vago ('não sei', 'qualquer coisa'), direcione para Clínico Geral.",
        "STATUS_CONSULTA": "Descobrir se é a PRIMEIRA VEZ do paciente na clínica ou se é um RETORNO (Se for criança, confirme a idade).",
        "FORMA_PAGAMENTO": "Descobrir se o atendimento será Particular ou por Plano de Saúde.",
        "AGENDAMENTO": f"Fazer o paciente escolher um horário: {vagas_txt}.",
        "DADOS_NOME": "Coletar o Nome Completo.",
        "DADOS_CPF": "Coletar os 11 números do CPF."
    }

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, Concierge de Saúde de elite da {NOME_CLINICA}.
ESTADO DO FUNIL: {estado_atual}
MISSÃO ATUAL: {mapa_objetivos.get(estado_atual)}

🏥 MAPEAMENTO RÁPIDO DE SINTOMAS (USE ISTO):
- Estômago/azia/gastrite -> Gastroenterologista
- Cabeça -> Neurologista
- Peito -> Cardiologista
- Dente -> Dentista
- Visão/Olhos -> Oftalmologista
- Ansiedade/Emocional -> Psicólogo
- Muscular/Coluna/Osso -> Ortopedista
- Check-up / Não sabe -> Clínico Geral

🛡️ REGRAS DE ELITE (V26):
1. DIRETO AO PONTO: Identificou o sintoma? Responda: "Perfeito. Para esse caso, o ideal é atendimento com um [ESPECIALISTA]." E na MESMA frase puxe a próxima pergunta do funil (ex: é a primeira vez?).
2. NÃO DIAGNOSTIQUE: Apenas direcione para o especialista.
3. CONTROLE TOTAL: Se o paciente desviar o assunto, diga: "Consigo te ajudar com isso depois, mas primeiro vamos garantir seu atendimento." e repita a pergunta.
4. PROIBIDO: "Entendo", "Compreendo", "Lamento". Seja rápida, resolutiva e profissional.

Retorne APENAS JSON:
{{
    "forneceu_dado_correto": true ou false,
    "resposta_concierge": "Sua resposta aplicando o mapeamento rápido e puxando para a próxima etapa. (Vazio se true)",
    "dado_extraido": "O dado puro identificado ou null"
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
    except: return {"forneceu_dado_correto": True, "resposta_concierge": "", "dado_extraido": mensagem_paciente}

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

        # 1. ABERTURA PADRÃO DE ELITE
        if not row:
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            cur.execute("INSERT INTO sessoes (telefone, estado, ultima_msg) VALUES (%s, %s, %s)", (telefone, estado, msg_clean))
            conn.commit()
            enviar_whatsapp(telefone, f"Olá! Seja bem-vindo(a) à {NOME_CLINICA}. Sou a {NOME_ATENDENTE} e vou te ajudar com seu atendimento agora. Para te direcionar corretamente, me diga: qual é o sintoma ou o tipo de consulta que você precisa?")
            return "OK", 200
        else: estado, nome, cpf, sintoma, horario, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_txt = ", ".join([v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in cur.fetchall()])

        # 2. ESCUDOS (URGÊNCIA E LGPD)
        emergencias = ["infarto", "morrendo", "falta de ar", "sangramento grave", "dor muito forte", "socorro", "desmaiou"]
        if any(p in msg_lower for p in emergencias):
            enviar_whatsapp(telefone, "🚨 Isso pode ser uma situação de urgência. Procure imediatamente um pronto atendimento ou ligue para o SAMU (192).")
            return "OK", 200

        if any(p in msg_lower for p in ["recepção", "pessoalmente", "na hora"]) and estado == "DADOS_CPF":
            cur.execute("UPDATE agenda SET disponivel=FALSE WHERE CAST(hora AS TEXT) LIKE %s", (f"{horario}%",))
            cur.execute("UPDATE sessoes SET estado='CONFIRMADO', cpf='NA_RECEPÇÃO' WHERE telefone=%s", (telefone,))
            conn.commit()
            enviar_whatsapp(telefone, f"Perfeito! Reserva para as {horario} confirmada. Pode informar os dados na recepção. Deseja marcar para mais alguém?")
            return "OK", 200

        # 3. ANALISE IA E FAST MAPPING
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, sintoma, horario)
        if not analise.get("forneceu_dado_correto"):
            enviar_whatsapp(telefone, analise.get("resposta_concierge", "Poderia ser um pouco mais específico?"))
            return "OK", 200

        dado_limpo = str(analise.get("dado_extraido", msg_clean))

        # 4. MOTOR DE PROGRESSÃO (O FECHAMENTO)
        if estado == "TRIAGEM":
            sintoma, estado = dado_limpo, "STATUS_CONSULTA"
            resposta = analise.get("resposta_concierge") or "Perfeito. Já identifiquei a especialidade. Esta será sua primeira consulta conosco ou é um retorno?"
            if not analise.get("resposta_concierge"):
                 resposta = "Perfeito. Esta será sua primeira consulta conosco ou é um retorno?"

        elif estado == "STATUS_CONSULTA":
            sintoma = f"{sintoma} | Status: {dado_limpo}"
            estado = "FORMA_PAGAMENTO"
            resposta = "O atendimento será particular ou através de convênio/plano de saúde?"

        elif estado == "FORMA_PAGAMENTO":
            sintoma = f"{sintoma} | Pgto: {dado_limpo}"
            estado = "AGENDAMENTO"
            resposta = f"Nossos horários disponíveis hoje são: {vagas_txt}. Qual deles funciona melhor para você?"

        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', dado_limpo)
            if match:
                h_final = next((v for v in vagas_txt.split(", ") if v.startswith(match.group(1).zfill(2))), None)
                if h_final:
                    horario, estado = h_final, "DADOS_NOME"
                    resposta = f"Horário das {horario} reservado. Qual o nome completo do paciente?"
                else: resposta = f"Horários disponíveis: {vagas_txt}"
            else: resposta = f"Qual horário deseja: {vagas_txt}?"

        elif estado == "DADOS_NOME":
            nome, estado = dado_limpo, "DADOS_CPF"
            resposta = "Para finalizar, digite os 11 números do CPF (ou avise se prefere dar na recepção)."

        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', dado_limpo)
            if len(cpf_limpo) == 11:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE CAST(hora AS TEXT) LIKE %s", (f"{horario}%",))
                resposta = f"Tudo pronto! Seu agendamento para as {horario} está confirmado. Deseja marcar para mais alguém?"
            else: resposta = "Por favor, digite os 11 números do CPF."

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
    return "✅ RESET V26 OK"

@app.route('/')
def home(): return "🚀 V26 ATIVA - FINAL DE MERCADO"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
