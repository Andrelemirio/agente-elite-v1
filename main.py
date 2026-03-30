# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V13 — AGENTE DE ELITE COM IA
# ARQUITETURA HÍBRIDA: CONTROLE POSTGRES + CÉREBRO OPENAI
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V13 - CÉREBRO IA ATIVO")

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

# =========================
# INTEGRAÇÕES (WHATSAPP E OPENAI)
# =========================
def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
    except Exception as e:
        print("Erro WhatsApp:", e)

def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt):
    """Cérebro da OpenAI para interpretar contexto e empatia"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    prompt_sistema = f"""Você é o Recepcionista Sênior de uma clínica médica de altíssimo padrão. 
Sua função é ser EXTREMAMENTE humano, empático e inteligente.
O paciente está na etapa de fornecer: {estado_atual}.
Horários disponíveis hoje: {vagas_txt}.

Analise a mensagem do paciente: "{mensagem_paciente}".
Ele respondeu o que foi pedido para a etapa atual ou fez uma pergunta/comentário avulso?

Responda OBRIGATORIAMENTE em JSON válido com a seguinte estrutura:
{{
    "forneceu_dado_correto": true ou false,
    "resposta_empatica": "Se ele NÃO forneceu o dado e fez uma pergunta (ex: 'posso tirar uma dúvida?', 'hemorroida dói'), responda com empatia, acolhimento, tire a dúvida e, na mesma mensagem, volte a pedir gentilmente a informação de {estado_atual}. Se ele respondeu corretamente, deixe vazio.",
    "dado_extraido": "Se ele forneceu a informação, extraia-a de forma limpa. Senão, null."
}}"""

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "system", "content": prompt_sistema}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        dados = res.json()
        conteudo = dados['choices'][0]['message']['content']
        return json.loads(conteudo)
    except Exception as e:
        print(f"Erro OpenAI: {e}")
        # Fallback de segurança se a IA falhar
        return {"forneceu_dado_correto": True, "resposta_empatica": "", "dado_extraido": mensagem_paciente}

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

        # 1. OVERRIDE GLOBAL (Interrupções Críticas)
        if any(p in msg_clean.lower() for p in ["início", "inicio", "recomeçar", "voltar", "cancelar"]) and estado != "TRIAGEM":
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            resposta = "Compreendido. Cancelei a operação. Como posso te ajudar agora? Qual é a especialidade ou sintoma do paciente?"
            cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        # 2. ANÁLISE NEURAL (O Cérebro Híbrido atua aqui)
        analise = analisar_com_ia(msg_clean, estado, vagas_txt)
        
        # Se a IA identificou que o paciente fez uma pergunta/desvio de assunto:
        if not analise.get("forneceu_dado_correto"):
            resposta = analise.get("resposta_empatica", "Desculpe, não entendi. Podemos voltar ao agendamento?")
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
        
        # Se a IA validou que o paciente respondeu corretamente, o dado segue para o Motor:
        dado_limpo = analise.get("dado_extraido", msg_clean)
        resposta = ""

        # 3. FLUXO DE ESTADOS SEGUROS
        if estado == "TRIAGEM":
            sintoma = dado_limpo
            estado = "AGENDAMENTO"
            if not vagas_lista:
                resposta = "Entendi o quadro. Infelizmente nossa agenda para hoje lotou. Deseja que eu adicione o paciente na lista de espera?"
                estado = "LISTA_ESPERA"
            else:
                resposta = f"Compreendo perfeitamente. Nossos horários livres hoje são: {vagas_txt}. Qual desses fica melhor para garantirmos o atendimento?"

        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', str(dado_limpo))
            if match:
                h_dig = match.group(1).zfill(2)
                h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
                if h_final:
                    horario, estado = h_final, "DADOS_NOME"
                    resposta = f"Ótima escolha! O horário das {horario} está reservado para você. Agora, por favor, me diga o nome completo do paciente."
                else:
                    resposta = f"Esse horário não está na lista atual. Por favor, escolha entre: {vagas_txt}."
            else:
                resposta = f"Para garantirmos a sua vaga agora, por favor, me confirme apenas o número do horário desejado: {vagas_txt}"

        elif estado == "DADOS_NOME":
            nome, estado = dado_limpo, "DADOS_CPF"
            primeiro_nome = nome.split()[0] if nome else "Paciente"
            resposta = f"Muito prazer, {primeiro_nome}. Para finalizar o seu prontuário com segurança, peço que digite apenas os 11 números do CPF do paciente."

        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', str(dado_limpo))
            if len(cpf_limpo) != 11:
                resposta = "O CPF informado parece estar incompleto. Poderia digitar os 11 números corretamente?"
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Tudo certo! Seu agendamento para as {horario} está 100% confirmado na clínica. Deseja marcar consulta para mais alguém da família?"

        elif estado == "CONFIRMADO":
            if any(p in str(dado_limpo).lower() for p in ["sim", "quero", "pessoas", "pessoa", "mais"]):
                estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
                resposta = "Será um prazer! Vamos iniciar o novo agendamento. Qual é a especialidade ou sintoma do próximo paciente?"
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

# =========================
# RESET / HOME
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = None
    try:
        conn = conectar(); cur = conn.cursor()
        cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
        for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "✅ RESET V13 OK", 200
    except Exception as e: return str(e), 500
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 IMPÉRIO DE SILÍCIO V13 (CÉREBRO IA) ATIVO", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
