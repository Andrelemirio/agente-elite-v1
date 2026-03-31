# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V19 — AGENTE DE ELITE PREMIUM
# GPS DE OBJETIVOS + ESCUDOS JURÍDICOS + ANTI-CLICHÊ
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V19 - ELITE PREMIUM ATIVO")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DO CLIENTE (CLÍNICA)
# =========================
NOME_CLINICA = os.environ.get("NOME_CLINICA", "Império Saúde").strip()
NOME_ATENDENTE = os.environ.get("NOME_ATENDENTE", "Ana").strip()
TIPO_CLINICA = os.environ.get("TIPO_CLINICA", "AMBOS").strip().upper() # AMBOS, PARTICULAR, ou PLANO

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
# 🧠 CÉREBRO DE IA (MEGA MOTOR GPT-4o COM GPS)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, sintoma_atual, horario_atual):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    contexto = f"Sintoma/Especialidade: '{sintoma_atual}'. Horário reservado: '{horario_atual}'." if sintoma_atual else "Ainda não sabemos o sintoma."
    
    # GPS DE OBJETIVOS (Para a IA nunca mais se perder ou pedir a coisa errada)
    mapa_objetivos = {
        "TRIAGEM": "Seu objetivo agora é descobrir APENAS o sintoma ou especialidade médica. Não peça nome nem horário ainda.",
        "FORMA_PAGAMENTO": "Seu objetivo agora é descobrir se o atendimento será Particular ou por Plano de Saúde.",
        "AGENDAMENTO": f"Seu objetivo agora é fazer o paciente escolher um destes horários: {vagas_txt}.",
        "DADOS_NOME": "Seu objetivo agora é pedir o nome completo do paciente.",
        "DADOS_CPF": "Seu objetivo agora é pedir o CPF (11 números)."
    }
    objetivo_atual = mapa_objetivos.get(estado_atual, "Avançar no atendimento.")

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, Concierge de Saúde premium da {NOME_CLINICA}.
ESTADO ATUAL DO FUNIL: {estado_atual}
SUA MISSÃO IMEDIATA: {objetivo_atual}

Contexto atual: {contexto}
Mensagem do paciente: "{mensagem_paciente}"

🛡️ REGRAS INQUEBRÁVEIS (PUNIÇÃO SE DESCUMPRIR):
1. PALAVRAS PROIBIDAS: NUNCA use as palavras "Entendo", "Compreendo", "Desculpe", "Sinto muito" ou "Certo". Fale direto e com elegância. Exemplo: se ele reclamar, diga "Tem razão. Vamos resolver isso. Qual é a sua especialidade?"
2. FOCO NO OBJETIVO: Se o paciente enviou uma mensagem vaga (ex: "Quero uma consulta"), ele NÃO cumpriu o objetivo. Você deve retornar "forneceu_dado_correto": false e FAZER A PERGUNTA do seu objetivo atual.
3. BLINDAGEM CFM E ASSUNTOS: Não prescreva, não diagnostique e corte assuntos fora da clínica com firmeza, puxando de volta para o objetivo atual.
4. DISCRIÇÃO: Nunca repita a doença do paciente.

Retorne APENAS um JSON válido:
{{
    "forneceu_dado_correto": true ou false (true APENAS SE ele respondeu diretamente à SUA MISSÃO IMEDIATA. Qualquer outra coisa é false),
    "resposta_concierge": "Sua resposta cortando desvios, tirando dúvidas e FINALIZANDO com a pergunta da sua Missão Imediata. (Vazio se true)",
    "dado_extraido": "O dado puro que ele passou (ex: a especialidade, a forma de pagamento, o nome) ou null"
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
        msg_lower = msg_clean.lower()

        conn = conectar()
        cur = conn.cursor()

        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        row = cur.fetchone()

        # 1. BOAS-VINDAS
        if not row:
            estado, nome, cpf, sintoma, horario, ultima_msg = "TRIAGEM", None, None, None, None, msg_clean
            cur.execute("INSERT INTO sessoes (telefone, estado, ultima_msg) VALUES (%s, %s, %s)", (telefone, estado, ultima_msg))
            conn.commit()
            resposta = f"Olá! Sou a {NOME_ATENDENTE}, concierge digital da {NOME_CLINICA}. Como posso cuidar da sua saúde hoje?"
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        vagas_lista = [v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in raw_vagas if v[0]]
        vagas_txt = ", ".join(vagas_lista) if vagas_lista else ""

        # 2. BLINDAGENS NATIVAS
        gatilhos_emergencia = ["passando mal", "infartando", "dor no peito", "explodir", "socorro", "morrendo", "acidente", "sangrando", "agonia"]
        if any(p in msg_lower for p in gatilhos_emergencia):
            resposta = "🚨 *ATENÇÃO:* Este é um canal exclusivamente administrativo e não realiza pronto-atendimento. Pelo seu relato, ligue imediatamente para o *SAMU (192)* ou dirija-se ao Pronto Socorro mais próximo."
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        if any(p in msg_lower for p in ["início", "inicio", "recomeçar", "voltar do zero", "cancelar tudo"]) and estado != "TRIAGEM":
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            resposta = "Feito. Cancelei o atendimento anterior. Qual é o sintoma ou especialidade para começarmos?"
            cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        if any(p in msg_lower for p in ["espera", "aguarda", "um momento", "vou procurar", "vou pegar", "ja volto", "já volto"]):
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, "Sem pressa, faça no seu tempo. Fico no aguardo.")
            return "OK", 200

        recusa_cpf = ["não vou", "nao vou", "não posso", "nao posso", "não quero", "recuso"]
        if estado == "DADOS_CPF" and any(p in msg_lower for p in recusa_cpf):
            cpf, estado = "RECUSADO_LGPD", "CONFIRMADO"
            cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
            resposta = f"Totalmente compreensível. Mantive sua reserva para as {horario}. Você pode fornecer o documento na recepção ao chegar. Agendamento confirmado! Deseja marcar para mais alguém?"
            cur.execute("UPDATE sessoes SET estado=%s, cpf=%s, ultima_msg=%s WHERE telefone=%s", (estado, cpf, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        # AMNÉSIA & MULTI AGENDAMENTOS
        if estado == "CONFIRMADO":
            if any(p in msg_lower for p in ["sim", "ssim", "quero", "pessoas", "pessoa", "mais", "ok", "pode", "marcar"]):
                estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
                resposta = "Excelente! Qual é a especialidade ou o sintoma desta pessoa?"
                cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
                conn.commit()
                enviar_whatsapp(telefone, resposta)
                return "OK", 200
            elif any(p in msg_lower for p in ["não", "nao", "obrigado", "tchau", "valeu"]):
                resposta = f"A {NOME_CLINICA} agradece a confiança. Um excelente dia!"
                enviar_whatsapp(telefone, resposta)
                return "OK", 200
            else:
                estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
                resposta = f"Olá novamente! Aqui é a {NOME_ATENDENTE} da {NOME_CLINICA}. Como posso te ajudar com a sua saúde hoje?"
                cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
                conn.commit()
                enviar_whatsapp(telefone, resposta)
                return "OK", 200

        # 3. AVALIAÇÃO DO CÉREBRO GPT-4o
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, sintoma, horario)
        
        if not analise.get("forneceu_dado_correto"):
            resposta = analise.get("resposta_concierge", "Pode repetir de forma mais clara, por favor?")
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
        
        dado_extraido = analise.get("dado_extraido")
        dado_limpo = str(dado_extraido) if dado_extraido is not None else msg_clean
        resposta = ""

        # 4. MOTOR DE FLUXO ADAPTÁVEL
        if estado == "TRIAGEM":
            sintoma = dado_limpo
            if TIPO_CLINICA == "AMBOS":
                estado = "FORMA_PAGAMENTO"
                resposta = "Certo. O atendimento será particular ou através de plano de saúde?"
            elif TIPO_CLINICA == "PLANO":
                estado = "FORMA_PAGAMENTO"
                resposta = "Certo. Para adiantarmos a liberação, qual é o seu convênio médico?"
            else:
                estado = "AGENDAMENTO"
                if not vagas_lista:
                    resposta = "Nossa agenda particular de hoje já está completa. Gostaria de entrar na lista de espera?"
                    estado = "LISTA_ESPERA"
                else:
                    resposta = f"Certo. Nossos atendimentos são particulares. Os horários livres hoje são: {vagas_txt}. Qual prefere?"

        elif estado == "FORMA_PAGAMENTO":
            sintoma = f"{sintoma} | Pagamento: {dado_limpo}"
            estado = "AGENDAMENTO"
            if not vagas_lista:
                resposta = "Nossa agenda para hoje já está completa. Gostaria de entrar na lista de espera prioritária?"
                estado = "LISTA_ESPERA"
            else:
                resposta = f"Perfeito. Nossos horários livres hoje são: {vagas_txt}. Qual deles fica melhor na sua rotina?"

        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', dado_limpo)
            if match:
                h_dig = match.group(1).zfill(2)
                h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
                if h_final:
                    horario, estado = h_final, "DADOS_NOME"
                    resposta = f"Ótimo. O horário das {horario} está reservado. Qual é o nome completo do paciente?"
                else:
                    resposta = f"Esse horário específico não temos mais hoje. Por favor, escolha entre: {vagas_txt}."
            else:
                resposta = f"Para garantirmos logo a sua vaga, me confirme apenas o número do horário desejado: {vagas_txt}"

        elif estado == "DADOS_NOME":
            nome, estado = dado_limpo, "DADOS_CPF"
            primeiro_nome = nome.split()[0] if nome else "Paciente"
            resposta = f"Muito prazer, {primeiro_nome}. Para criarmos sua ficha com segurança, digite apenas os 11 números do seu CPF (ou me avise se preferir informar na recepção)."

        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', dado_limpo)
            if len(cpf_limpo) != 11:
                resposta = "O CPF parece incompleto. Poderia digitar os 11 números novamente para a validação?"
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Tudo pronto! Agendamento para as {horario} 100% confirmado. Quer aproveitar e marcar para mais alguém?"

        elif estado == "LISTA_ESPERA":
            if any(p in dado_limpo.lower() for p in ["sim", "quero", "pode", "ok"]):
                estado, resposta = "CONFIRMADO", "Feito. Você está na lista de espera. Entraremos em contato no segundo que vagar um horário!"
            else:
                estado, resposta = "TRIAGEM", "Tranquilo. Caso precise de algo mais, estou à disposição."

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
        return "✅ RESET V19 OK", 200
    except Exception as e: return str(e), 500
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 IMPÉRIO DE SILÍCIO V19 (ELITE PREMIUM) ATIVO", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
