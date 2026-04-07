# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V39 — ODONTO SILÍCIO (CONCIERGE DE ELITE)
# INSTRUÇÃO DINÂMICA E CORREÇÃO DE ESTADO
# ============================================

import os
import requests
import psycopg2
import json
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V39 - ODONTO SILÍCIO ATIVA")

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
# 🧠 CÉREBRO GPT-4o SÊNIOR ODONTOLÓGICO
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, dados_acumulados):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    instrucoes = {
        "TRIAGEM": "AÇÃO OBRIGATÓRIA: Analise o procedimento desejado (limpeza, dor, avaliação, etc). Diga que agendará a avaliação/consulta. Termine perguntando se é PRIMEIRA VEZ na clínica. (Defina novo_estado: STATUS_CONSULTA)",
        "STATUS_CONSULTA": "AÇÃO OBRIGATÓRIA: Agradeça e pergunte se é PARTICULAR ou PLANO. (Defina novo_estado: FORMA_PAGAMENTO)",
        "FORMA_PAGAMENTO": f"AÇÃO OBRIGATÓRIA: Ofereça os horários {vagas_txt} e peça para escolher. (Defina novo_estado: AGENDAMENTO)",
        "AGENDAMENTO": "AÇÃO OBRIGATÓRIA: O paciente escolheu o horário. Confirme a reserva e peça o NOME COMPLETO. (Defina novo_estado: DADOS_NOME)",
        "DADOS_NOME": "AÇÃO OBRIGATÓRIA: O paciente informou o NOME. Chame-o pelo nome, agradeça e peça o CPF (avise que pode dar na recepção). (Defina novo_estado: DADOS_CPF)",
        "DADOS_CPF": "AÇÃO OBRIGATÓRIA: O paciente informou o CPF. Confirme a reserva do horário. (Defina novo_estado: CONFIRMADO)",
        "CONFIRMADO": "AÇÃO OBRIGATÓRIA: Pergunte educadamente se ficou alguma dúvida ou se há mais alguém da família que deseja agendar. (Defina novo_estado: AGENDAMENTO se ele quiser prosseguir)"
    }
    
    instrucao_atual = instrucoes.get(estado_atual, "AÇÃO OBRIGATÓRIA: Continue o atendimento com empatia e tente extrair o dado que falta.")

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, a recepcionista virtual de elite e Concierge da clínica {NOME_CLINICA}. Seu tom de voz é extremamente acolhedor, sofisticado, humanizado e focado em excelência.

DADOS DO PACIENTE: {dados_acumulados}
ESTADO ATUAL DO SISTEMA: {estado_atual}
HORÁRIOS DISPONÍVEIS: {vagas_txt}

REGRAS DE OURO:
1. NUNCA pergunte 'o que está sentindo' de forma genérica como um pronto-socorro médico.
2. Se o paciente não especificar, pergunte de forma educada qual procedimento ele tem interesse (ex: avaliação geral, limpeza, clareamento, lentes de contato dental, implantes) ou se está com algum desconforto específico nos dentes.
3. Mantenha as respostas curtas, diretas e naturais. NUNCA envie blocos gigantes de texto.
4. Sempre conduza o paciente para o agendamento de forma elegante.

SUA MISSÃO EXATA NESTE SEGUNDO:
{instrucao_atual}

Retorne APENAS um JSON:
{{
    "resposta_para_paciente": "Sua resposta sênior, fluida e natural cumprindo a missão acima",
    "novo_estado": "O estado exato solicitado na missão",
    "resumo_dados": "Atualize os dados coletados de forma resumida, mantendo o histórico"
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
            enviar_whatsapp(telefone, f"Olá! Seja muito bem-vindo(a) à {NOME_CLINICA}. Meu nome é {NOME_ATENDENTE} e sou a sua concierge digital. É um prazer receber você. Como posso te ajudar a conquistar o seu melhor sorriso hoje?")
            return "OK", 200
        else: 
            estado, dados_acumulados, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_txt = ", ".join([v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in cur.fetchall()])

        emergencias = ["dor insuportável", "sangramento forte", "socorro", "dor extrema", "urgência"]
        if any(p in msg_lower for p in emergencias):
            enviar_whatsapp(telefone, "🚨 Identifiquei sinais de urgência odontológica. Para casos de dor extrema ou sangramento, por favor, dirija-se imediatamente a um pronto atendimento odontológico.")
            return "OK", 200

        # --- ANÁLISE IA ---
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, dados_acumulados)
        if not analise:
            enviar_whatsapp(telefone, "Tivemos uma pequena instabilidade no sistema. Poderia repetir, por favor?")
            return "OK", 200

        resposta = analise.get("resposta_para_paciente", "Pode me explicar melhor?")
        novo_estado = analise.get("novo_estado", estado)
        novos_dados = analise.get("resumo_dados", dados_acumulados)

        # --- INTERCEPTADORES DE FORÇA BRUTA ---
        ordem_estados = {"TRIAGEM": 1, "STATUS_CONSULTA": 2, "FORMA_PAGAMENTO": 3, "AGENDAMENTO": 4, "DADOS_NOME": 5, "DADOS_CPF": 6, "CONFIRMADO": 7}
        
        match_horario = re.search(r'\b(9|09|11|14|16)\b', msg_clean)
        if estado in ["FORMA_PAGAMENTO", "AGENDAMENTO"] and match_horario:
            hora_formatada = match_horario.group(1).zfill(2) + ":00"
            novo_estado = "DADOS_NOME"
            novos_dados = f"{dados_acumulados} | Horário escolhido: {hora_formatada}"
            resposta = f"Perfeito! O horário das {hora_formatada} está reservado para você. Agora, por favor, poderia me informar o seu nome completo?"

        elif estado == "DADOS_CPF":
            if any(p in msg_lower for p in ["não", "nao", "dia", "recepção", "recepcao", "depois", "lá"]):
                novo_estado = "CONFIRMADO"
                resposta = "Sem problemas, você pode informar o CPF no dia da sua avaliação. O seu agendamento está 100% confirmado! Ficou mais alguma dúvida ou há mais alguém da família que deseja agendar?"
            elif len(re.sub(r'\D', '', msg_clean)) >= 11:
                novo_estado = "CONFIRMADO"
                resposta = "CPF recebido com sucesso! Seu agendamento está 100% confirmado. Ficou mais alguma dúvida ou há mais alguém da família que deseja agendar?"

        elif ordem_estados.get(novo_estado, 0) < ordem_estados.get(estado, 0):
            if estado == "CONFIRMADO" and novo_estado in ["AGENDAMENTO", "TRIAGEM", "FORMA_PAGAMENTO"]:
                pass 
            else:
                novo_estado = estado 

        # --- ATUALIZAÇÃO DA AGENDA ---
        if novo_estado == "CONFIRMADO" and estado != "CONFIRMADO":
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
