# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V14 — AGENTE DE ELITE
# CÉREBRO IA COM MEMÓRIA E BLINDAGEM CLÍNICA
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V14 - CÉREBRO BLINDADO ATIVO")

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

def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
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
    except Exception as e:
        print("Erro DB:", e)
    finally:
        if conn: conn.close()

init_db()

def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
    except Exception as e:
        print("Erro WhatsApp:", e)

# =========================
# CÉREBRO DE IA (OPENAI)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, sintoma_atual, horario_atual):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    # Contexto dinâmico para a IA saber o que está acontecendo na conversa
    contexto = f"Sintoma relatado antes: '{sintoma_atual}'. Horário já reservado: '{horario_atual}'." if sintoma_atual else "Nenhum sintoma definido ainda."
    
    prompt_sistema = f"""Você é um Recepcionista Concierge de uma clínica médica premium. Seja direto, educado, ágil e muito natural (não pareça um robô).
Você está tentando coletar a seguinte informação do paciente agora: {estado_atual}.
{contexto}
Horários que temos hoje: {vagas_txt}.

A mensagem do paciente foi: "{mensagem_paciente}".

REGRAS CRÍTICAS DE CONDUTA:
1. Se o paciente fez uma pergunta que NÃO tem relação NENHUMA com saúde, medicina ou a clínica (ex: como ficar rico, política, dicas gerais), responda educadamente que você é da recepção médica e não pode ajudar com isso.
2. Se o paciente perguntar sobre o agendamento atual (ex: "para qual médico é?"), use o 'Sintoma relatado antes' para dizer o especialista (ex: dor no estômago = Gastroenterologista, pênis = Urologista, coração = Cardiologista, etc).
3. NUNCA use frases clichês robóticas como "Entendo sua dúvida", "Compreendo perfeitamente", ou "Por favor, me forneça seu...". Fale como um humano de alto nível.
4. Responda à dúvida primeiro (de forma breve) e, na mesma frase, conduza suavemente de volta para coletar o dado que falta ({estado_atual}).

Retorne OBRIGATORIAMENTE um JSON válido:
{{
    "forneceu_dado_correto": true ou false (true apenas se ele respondeu o que você precisa para o estado atual, false se ele fez pergunta/desviou),
    "resposta_concierge": "Sua resposta humana e direta tirando a dúvida e pedindo o dado de volta (deixe vazio se ele forneceu o dado)",
    "dado_extraido": "A informação que ele deu (ex: o nome, o CPF, o número do horário) ou null"
}}"""

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "system", "content": prompt_sistema}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2 # Baixa temperatura para ele ser mais preciso e menos criativo/prolixo
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return {"forneceu_dado_correto": True, "resposta_concierge": "", "dado_extraido": mensagem_paciente}

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200

        telefone = data.get("phone", "")
        if "@" in telefone: telefone = telefone.split("@")[0]

        msg = ""
        if "text" in data:
            msg = data["text"].get("message", "") if isinstance(data["text"], dict) else str(data["text"])
        elif "message" in data:
            msg = str(data["message"])

        if not telefone or not msg: return "OK", 200
        msg_clean = msg.strip()

        conn = conectar()
        cur = conn.cursor()

        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        row = cur.fetchone()

        if not row:
            estado, nome, cpf, sintoma, horario, ultima_msg = "TRIAGEM", None, None, None, None, None
            cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, %s)", (telefone, estado))
            conn.commit()
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        vagas_lista = [v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in raw_vagas if v[0]]
        vagas_txt = ", ".join(vagas_lista) if vagas_lista else ""

        # 1. OVERRIDE GLOBAL
        if any(p in msg_clean.lower() for p in ["início", "inicio", "recomeçar", "voltar", "cancelar"]) and estado != "TRIAGEM":
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            resposta = "Tudo bem, cancelei o processo anterior. Vamos começar do zero. Qual é a especialidade ou o sintoma do paciente?"
            cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        # 2. ANÁLISE NEURAL (Agora com memória de contexto)
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, sintoma, horario)
        
        # Se a IA identificou desvio:
        if not analise.get("forneceu_dado_correto"):
            resposta = analise.get("resposta_concierge", "Pode repetir, por favor? Acabei não entendendo.")
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
        
        # Se validou, segue o fluxo do motor:
        dado_limpo = analise.get("dado_extraido", msg_clean)
        resposta = ""

        if estado == "TRIAGEM":
            sintoma = str(dado_limpo)
            estado = "AGENDAMENTO"
            if not vagas_lista:
                resposta = "Nossa agenda para hoje lotou. Deseja que eu adicione o paciente na lista de espera?"
                estado = "LISTA_ESPERA"
            else:
                resposta = f"Certo, já entendi a necessidade. Nossos horários livres hoje são: {vagas_txt}. Qual deles fica melhor para você?"

        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', str(dado_limpo))
            if match:
                h_dig = match.group(1).zfill(2)
                h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
                if h_final:
                    horario, estado = h_final, "DADOS_NOME"
                    resposta = f"Ótimo. O horário das {horario} está reservado. Qual é o nome completo do paciente?"
                else:
                    resposta = f"Esse horário não está na lista. Por favor, escolha entre: {vagas_txt}."
            else:
                resposta = f"Para garantirmos a vaga, me confirme apenas o número do horário desejado: {vagas_txt}"

        elif estado == "DADOS_NOME":
            nome, estado = str(dado_limpo), "DADOS_CPF"
            primeiro_nome = nome.split()[0] if nome else "Paciente"
            resposta = f"Muito prazer, {primeiro_nome}. Para finalizar o cadastro, digite apenas os 11 números do seu CPF."

        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', str(dado_limpo))
            if len(cpf_limpo) != 11:
                resposta = "O CPF parece incompleto. Poderia digitar os 11 números novamente?"
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Tudo pronto! Agendamento para as {horario} 100% confirmado. Gostaria de marcar consulta para mais alguém da família?"

        elif estado == "CONFIRMADO":
            if any(p in str(dado_limpo).lower() for p in ["sim", "quero", "pessoas", "pessoa", "mais"]):
                estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
                resposta = "Combinado! Vamos iniciar o novo agendamento. Qual é a especialidade ou sintoma do próximo paciente?"
            else:
                resposta = "Perfeito. Nossa equipe agradece a preferência. Tenha um excelente dia!"

        # SALVAR ESTADO
        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print("Erro Webhook:", e)
    finally:
        if conn: conn.close()
    return "OK", 200

@app.route('/reset', methods=['GET'])
def reset():
    conn = None
    try:
        conn = conectar(); cur = conn.cursor()
        cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
        for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "✅ RESET V14 OK", 200
    except Exception as e: return str(e), 500
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 IMPÉRIO DE SILÍCIO V14 (CÉREBRO BLINDADO) ATIVO", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
