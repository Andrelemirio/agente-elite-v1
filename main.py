# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V32 — AGENTE DE ELITE (OMNIPRESENTE)
# RECONHECIMENTO UNIVERSAL DE MÚLTIPLAS DORES 
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V32 - OMNIPRESENTE ATIVO")

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
# 🧠 CÉREBRO GPT-4o (MULTI-PROCESSAMENTO)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, sintoma_atual, horario_atual):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    mapa_objetivos = {
        "TRIAGEM": "O paciente informará DORES. Sua missão: 1) Nomear o especialista exato para CADA SINTOMA relatado. 2) Terminar perguntando se é a PRIMEIRA VEZ dele na clínica ou um retorno.",
        "STATUS_CONSULTA": "Saber se é a primeira vez ou retorno. Terminar perguntando se o atendimento será PARTICULAR ou por PLANO DE SAÚDE.",
        "FORMA_PAGAMENTO": f"Saber se é Particular ou Plano. Terminar pedindo para ele escolher UM destes horários: {vagas_txt}.",
        "AGENDAMENTO": "Saber qual horário ele quer. Terminar pedindo o NOME COMPLETO.",
        "DADOS_NOME": "Saber o nome. Terminar pedindo os 11 números do CPF.",
        "DADOS_CPF": "Coletar o CPF."
    }

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, Concierge de Saúde da {NOME_CLINICA}.
ESTADO ATUAL DO FUNIL: {estado_atual}
O QUE VOCÊ DEVE FAZER AGORA: {mapa_objetivos.get(estado_atual)}

🛡️ REGRAS INFALÍVEIS (LEIA COM ATENÇÃO MÁXIMA):
1. MAPA DE MÉDICOS: Garganta = Otorrinolaringologista | Olhos/Visão = Oftalmologista | Cabeça = Neurologista | Costas/Ossos/Articulações = Ortopedista | Estômago = Gastroenterologista | Pele = Dermatologista.
2. PROCESSAMENTO MÚLTIPLO: Se o paciente falar 4 dores na mesma mensagem, você DEVE escrever na sua resposta o médico indicado para CADA UMA das 4 dores, sem ignorar nenhuma. Ex: "Para a cabeça é o Neuro, para a garganta é o Otorrino, etc."
3. INTERRUPÇÃO DE SINTOMA: Se o paciente falar de uma DOR NOVA em QUALQUER etapa do funil (mesmo que você esteja perguntando de CPF), você deve PRIMEIRO responder qual é o médico daquela dor, e depois repetir a pergunta da sua missão atual.
4. TOLERÂNCIA TOTAL: Ignore erros de digitação. Se ele falou de dor, retorne `forneceu_dado_correto: true` IMEDIATAMENTE.
5. PROIBIDO: Clichês ("Entendo", "Olá").

Retorne APENAS JSON:
{{
    "forneceu_dado_correto": true,
    "resposta_concierge": "O texto perfeito mapeando TODAS as dores citadas e puxando a pergunta da missão atual.",
    "dado_extraido": "O dado importante da mensagem"
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
    except: return {"forneceu_dado_correto": True, "resposta_concierge": "Poderia repetir, por favor?", "dado_extraido": mensagem_paciente}

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

        analise = analisar_com_ia(msg_clean, estado, vagas_txt, sintoma, horario)
        dado_limpo = str(analise.get("dado_extraido") or msg_clean)
        resposta = analise.get("resposta_concierge", "Poderia ser um pouco mais claro?")
        forneceu_correto = analise.get("forneceu_dado_correto", True) # FORÇANDO TRUE GLOBALMENTE PARA NÃO TRAVAR

        # BYPASS RÁPIDO PARA NÃO DEPENDER DA IA EM RESPOSTAS CURTAS
        if estado == "STATUS_CONSULTA" and any(p in msg_lower for p in ["primeira", "1", "retorno", "ja fui", "já fui"]):
            forneceu_correto = True
            if "primeira" in msg_lower or "1" in msg_lower: dado_limpo = "Primeira Vez"
            else: dado_limpo = "Retorno"
            
        elif estado == "FORMA_PAGAMENTO" and any(p in msg_lower for p in ["particular", "plano", "convenio", "unimed"]):
            forneceu_correto = True
            if "particular" in msg_lower: dado_limpo = "Particular"
            else: dado_limpo = "Plano de Saúde"

        if forneceu_correto:
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
    return "✅ RESET V32 OK"

@app.route('/')
def home(): return "🚀 V32 ATIVA - OMNIPRESENTE"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
