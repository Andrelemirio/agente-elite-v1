# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V39 — ODONTO SILÍCIO (CONCIERGE DE ELITE)
# LÓGICA CONDICIONAL E BLINDAGEM DE ESTADO
# ============================================

import os
import requests
import psycopg2
import json
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V39 - ODONTO SILÍCIO ATIVA E BLINDADA")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DO CLIENTE
# =========================
NOME_CLINICA = os.environ.get("NOME_CLINICA", "Odonto Silício").strip()
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
# 🧠 CÉREBRO GPT-4o SÊNIOR ODONTOLÓGICO CONDICIONAL
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, dados_acumulados):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    instrucoes = {
        "TRIAGEM": "AÇÃO: Identifique o procedimento desejado. Diga que agendará uma avaliação e pergunte se é PRIMEIRA VEZ. (novo_estado: STATUS_CONSULTA)",
        "STATUS_CONSULTA": "AÇÃO: Agradeça. Pergunte se a consulta será PARTICULAR ou pelo PLANO de saúde. (novo_estado: FORMA_PAGAMENTO)",
        "FORMA_PAGAMENTO": f"AÇÃO: Ofereça APENAS os horários {vagas_txt} e peça para escolher. (novo_estado: AGENDAMENTO)",
        "AGENDAMENTO": f"AÇÃO: SE o paciente escolheu claramente um horário, confirme e peça o NOME COMPLETO (novo_estado: DADOS_NOME). SE ele não escolheu o horário ou fez outra pergunta, responda educadamente e OFEREÇA OS HORÁRIOS NOVAMENTE (novo_estado: AGENDAMENTO).",
        "DADOS_NOME": "AÇÃO: SE o paciente forneceu o nome, chame-o pelo nome e peça o CPF para cadastro, avisando que pode dar na recepção (novo_estado: DADOS_CPF). SE ele não deu o nome, continue pedindo (novo_estado: DADOS_NOME).",
        "DADOS_CPF": "AÇÃO: SE o paciente informou o CPF ou recusou, confirme que o horário está reservado (novo_estado: CONFIRMADO). SE ele demonstrar que quer cancelar/desistir, seja educado e encerre o contato (novo_estado: CONFIRMADO).",
        "CONFIRMADO": "AÇÃO: O agendamento está concluído ou cancelado. Pergunte apenas se ficou alguma dúvida ou se há mais alguém da família para agendar. (novo_estado: CONFIRMADO)"
    }
    
    instrucao_atual = instrucoes.get(estado_atual, "AÇÃO: Continue o atendimento com empatia e resolva a dúvida.")

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, a Concierge de elite da clínica {NOME_CLINICA}. Seu tom é acolhedor, premium e focado.

DADOS DO PACIENTE: {dados_acumulados}
ESTADO ATUAL DO SISTEMA: {estado_atual}
HORÁRIOS DISPONÍVEIS: {vagas_txt}

REGRAS DE OURO:
1. NUNCA pergunte 'o que está sentindo' de forma genérica.
2. NUNCA avance o atendimento se o paciente fizer uma pergunta alheia. Responda a pergunta e repita a exigência da etapa atual.
3. Se o paciente perguntar de preços, diga que valores exatos só são passados após avaliação clínica.
4. Mantenha respostas naturais, curtas e elegantes.

SUA MISSÃO EXATA AGORA:
{instrucao_atual}

Retorne APENAS um JSON:
{{
    "resposta_para_paciente": "Sua resposta natural",
    "novo_estado": "O estado exato após sua análise",
    "resumo_dados": "Mantenha o histórico atualizado de forma resumida"
}}"""

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": mensagem_paciente}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except: return None

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
            enviar_whatsapp(telefone, f"Olá! Seja muito bem-vindo(a) à {NOME_CLINICA}. Meu nome é {NOME_ATENDENTE} e sou a sua concierge digital. Como posso ajudar a cuidar do seu sorriso hoje?")
            return "OK", 200
        else: 
            estado, dados_acumulados, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_txt = ", ".join([v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in cur.fetchall()])

        emergencias = ["dor insuportável", "sangramento forte", "socorro", "dor extrema", "urgência"]
        if any(p in msg_lower for p in emergencias):
            enviar_whatsapp(telefone, "🚨 Identifiquei sinais de urgência. Para casos de dor extrema ou sangramento forte, por favor, dirija-se imediatamente a um pronto atendimento odontológico.")
            return "OK", 200

        # --- ANÁLISE IA ---
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, dados_acumulados)
        if not analise:
            enviar_whatsapp(telefone, "Tivemos uma pequena instabilidade no sistema. Poderia repetir, por favor?")
            return "OK", 200

        resposta = analise.get("resposta_para_paciente", "Pode me explicar melhor?")
        novo_estado = analise.get("novo_estado", estado)
        novos_dados = analise.get("resumo_dados", dados_acumulados)

        # --- INTERCEPTADORES DE SEGURANÇA MÁXIMA ---
        ordem_estados = {"TRIAGEM": 1, "STATUS_CONSULTA": 2, "FORMA_PAGAMENTO": 3, "AGENDAMENTO": 4, "DADOS_NOME": 5, "DADOS_CPF": 6, "CONFIRMADO": 7}
        
        # 1. Bypass Rápido de Horário
        match_horario = re.search(r'\b(9|09|11|14|16)\b', msg_clean)
        if estado in ["FORMA_PAGAMENTO", "AGENDAMENTO"] and match_horario:
            hora_formatada = match_horario.group(1).zfill(2) + ":00"
            novo_estado = "DADOS_NOME"
            novos_dados = f"{dados_acumulados} | Horário escolhido: {hora_formatada}"
            resposta = f"Perfeito! O horário das {hora_formatada} está reservado para você. Agora, por favor, poderia me informar o seu nome completo?"

        # 2. Trava Anti-Alucinação (Impede a IA de pular a escolha do horário)
        if novo_estado == "DADOS_NOME" and estado == "AGENDAMENTO":
            if not any(h in novos_dados or h in msg_clean for h in ["09", "11", "14", "16", "9"]):
                novo_estado = "AGENDAMENTO" # Força ela a voltar e não avançar

        # 3. Bypass de CPF exato (se ele digitar números, avança. Se reclamar/negar, a IA resolve)
        elif estado == "DADOS_CPF":
            if len(re.sub(r'\D', '', msg_clean)) >= 11:
                novo_estado = "CONFIRMADO"
                resposta = "CPF recebido com sucesso! Seu agendamento está 100% confirmado. Ficou mais alguma dúvida ou há mais alguém da família que deseja agendar?"

        # 4. Trava de Ordem Lógica
        elif ordem_estados.get(novo_estado, 0) < ordem_estados.get(estado, 0):
            if estado == "CONFIRMADO" and novo_estado in ["AGENDAMENTO", "TRIAGEM", "FORMA_PAGAMENTO"]:
                pass 
            else:
                novo_estado = estado 

        # --- ATUALIZAÇÃO DA AGENDA ---
        if novo_estado == "CONFIRMADO" and estado != "CONFIRMADO":
            # Apenas atualiza se não for um cancelamento
            if not any(p in msg_lower for p in ["cancelar", "desisto", "outra", "nao vou"]):
                for h in ["09:00", "11:00", "14:30", "16:00"]:
                    if h in novos_dados or h in msg_clean:
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
    return "✅ RESET ODONTO SILÍCIO OK"

@app.route('/')
def home(): return "🚀 ODONTO SILÍCIO ATIVA"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
