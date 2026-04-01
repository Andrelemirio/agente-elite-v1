# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V33 — AGENTE SÊNIOR DE ELITE
# INTELIGÊNCIA LIVRE, EMPATIA CLÍNICA E CONTROLE TOTAL DA IA
# ============================================

import os
import requests
import psycopg2
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V33 - AGENTE SÊNIOR ATIVO")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DO CLIENTE
# =========================
NOME_CLINICA = os.environ.get("NOME_CLINICA", "Império Saúde").strip()
NOME_ATENDENTE = os.environ.get("NOME_ATENDENTE", "Ana").strip()

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
# 🧠 CÉREBRO GPT-4o SÊNIOR (CONTROLE TOTAL)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, dados_acumulados):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    prompt_sistema = f"""Você é {NOME_ATENDENTE}, uma Concierge Sênior e Especialista em Atendimento da clínica {NOME_CLINICA}. 
Você é humana, acolhedora, inteligente e tem vasta experiência em direcionamento médico.

DADOS DO PACIENTE ATÉ AGORA: {dados_acumulados}
ESTADO ATUAL DO FUNIL: {estado_atual}
HORÁRIOS DISPONÍVEIS: {vagas_txt}

SUA MISSÃO É CONDUZIR O PACIENTE PELO FUNIL ABAIXO, UMA ETAPA POR VEZ:
1. TRIAGEM: Acolha o paciente com empatia. Se ele falar de dores, analise TODAS. Diga de forma natural e sênior qual o médico para cada dor (Garganta=Otorrino, Olho=Oftalmo, Cabeça=Neuro, Costas=Ortopedista, Pele=Dermatologista, etc). Só depois de explicar, pergunte se é a primeira vez dele na clínica.
2. STATUS: Após saber se é a primeira vez, pergunte com educação se o atendimento será Particular ou por Plano de Saúde.
3. PAGAMENTO: Após ele informar o pagamento, ofereça os horários disponíveis e peça para ele escolher um.
4. AGENDAMENTO: Após ele escolher o horário, confirme e peça o Nome Completo.
5. NOME: Após ele dar o nome, chame-o pelo nome e peça o CPF (informe que ele pode dar na recepção se preferir).
6. CPF: Confirme o agendamento de forma acolhedora e encerre.

REGRAS DE CONDUTA SÊNIOR:
- ACOLHIMENTO: Nunca seja um robô frio. Demonstre cuidado com as dores relatadas ("Sinto muito que esteja com essas dores, vou te ajudar a resolver isso agora mesmo").
- INTELIGÊNCIA: Se o paciente falar várias coisas ao mesmo tempo, processe tudo de uma vez.
- FOCO: Sempre termine sua resposta com a pergunta que leva para a próxima etapa.

Retorne APENAS um JSON válido estruturado assim:
{{
    "resposta_para_paciente": "Sua resposta completa, empática e sênior",
    "novo_estado": "Atualize o estado para a etapa que você está buscando AGORA (TRIAGEM, STATUS_CONSULTA, FORMA_PAGAMENTO, AGENDAMENTO, DADOS_NOME, DADOS_CPF, CONFIRMADO)",
    "resumo_dados": "Atualize os dados que você já coletou do paciente"
}}"""

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": mensagem_paciente}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3 # Um pouco mais de criatividade para empatia
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except Exception as e: 
        print("Erro IA:", e)
        return None

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
        cur.execute("SELECT estado, sintoma, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        row = cur.fetchone()

        if not row:
            estado, dados_acumulados = "TRIAGEM", "Nenhum dado ainda."
            cur.execute("INSERT INTO sessoes (telefone, estado, sintoma, ultima_msg) VALUES (%s, %s, %s, %s)", (telefone, estado, dados_acumulados, msg_clean))
            conn.commit()
            enviar_whatsapp(telefone, f"Olá! Seja bem-vindo(a) à {NOME_CLINICA}. Meu nome é {NOME_ATENDENTE}. Estou aqui para cuidar do seu agendamento. Poderia me contar o que está sentindo ou qual especialista procura?")
            return "OK", 200
        else: 
            estado, dados_acumulados, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_txt = ", ".join([v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in cur.fetchall()])

        emergencias = ["infarto", "morrendo", "falta de ar", "sangramento", "dor insuportável", "socorro"]
        if any(p in msg_lower for p in emergencias):
            enviar_whatsapp(telefone, "🚨 Identifiquei sinais de urgência. Por favor, não espere. Dirija-se imediatamente a um pronto atendimento ou ligue para o SAMU (192).")
            return "OK", 200

        # --- O CÉREBRO ASSUME O CONTROLE ---
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, dados_acumulados)
        
        if not analise:
            enviar_whatsapp(telefone, "Tivemos uma pequena instabilidade no sistema. Poderia repetir, por favor?")
            return "OK", 200

        resposta = analise.get("resposta_para_paciente", "Pode me explicar melhor?")
        novo_estado = analise.get("novo_estado", estado)
        novos_dados = analise.get("resumo_dados", dados_acumulados)

        # Atualiza a vaga se o estado for confirmado e tiver horário nos dados
        if novo_estado == "CONFIRMADO":
            for h in ["09:00", "11:00", "14:30", "16:00"]:
                if h in novos_dados:
                    cur.execute("UPDATE agenda SET disponivel=FALSE WHERE CAST(hora AS TEXT) LIKE %s", (f"{h}%",))
                    break

        cur.execute("UPDATE sessoes SET estado=%s, sintoma=%s, ultima_msg=%s WHERE telefone=%s", (novo_estado, novos_dados, msg_clean, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e: print("Erro Webhook:", e)
    finally:
        if conn: conn.close()
    return "OK", 200

@app.route('/reset')
def reset():
    conn = conectar(); cur = conn.cursor()
    cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
    for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
    conn.commit(); conn.close()
    return "✅ RESET V33 OK - MODO SÊNIOR"

@app.route('/')
def home(): return "🚀 V33 ATIVA - AGENTE SÊNIOR"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
