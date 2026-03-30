# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V8.1 — AGENTE DE ELITE
# COMPLETO / BLINDADO PARA PRODUÇÃO
# ============================================

import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V8.1 ONLINE")

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

# =========================
# INIT DB
# =========================
def init_db():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                telefone TEXT PRIMARY KEY,
                estado TEXT,
                nome TEXT,
                cpf TEXT,
                sintoma TEXT,
                horario TEXT,
                ultima_msg TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                id SERIAL PRIMARY KEY,
                hora TEXT,
                disponivel BOOLEAN DEFAULT TRUE
            )
        """)

        conn.commit()
    except Exception as e:
        print("Erro DB:", e)
    finally:
        if conn:
            conn.close()

init_db()

# =========================
# WHATSAPP
# =========================
def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(
            url,
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
            json={"phone": telefone, "message": mensagem},
            timeout=10
        )
    except Exception as e:
        print("Erro WhatsApp:", e)

# =========================
# INTELIGÊNCIA
# =========================
RESET_PALAVRAS = [
    "começar", "inicio", "início", "reiniciar",
    "nova consulta", "outra consulta", "marcar outra",
    "quero marcar", "preciso marcar"
]

AGUARDAR_PALAVRAS = [
    "espera", "aguarde", "um momento", "vou ver", "ja volto"
]

def detectar_especialidade(s):
    s = s.lower()
    if "peito" in s or "coração" in s:
        return "Cardiologista"
    if "dente" in s:
        return "Dentista"
    if "estômago" in s or "barriga" in s:
        return "Gastroenterologista"
    return "Clínico Geral"

# =========================
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)

        if not data or data.get("fromMe"):
            return "OK", 200

        telefone = data.get("phone", "")
        if "@" in telefone:
            telefone = telefone.split("@")[0]

        # Extração blindada Z-API
        msg = ""
        if "text" in data:
            if isinstance(data["text"], dict):
                msg = data["text"].get("message", "")
            else:
                msg = str(data["text"])
        elif "message" in data:
            msg = str(data["message"])

        if not telefone or not msg:
            return "OK", 200

        msg = msg.strip()
        msg_lower = msg.lower()

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

        if msg == ultima_msg:
            return "OK", 200

        # Tratamento seguro da leitura da agenda do Postgres
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        vagas_lista = []
        for v in raw_vagas:
            if v[0] is not None:
                if hasattr(v[0], 'strftime'):
                    vagas_lista.append(v[0].strftime('%H:%M'))
                else:
                    vagas_lista.append(str(v[0])[:5])

        vagas_txt = ", ".join(vagas_lista) if vagas_lista else "sem vagas"
        resposta = ""

        # RESET GLOBAL
        if any(p in msg_lower for p in RESET_PALAVRAS) and estado != "TRIAGEM":
            estado = "TRIAGEM"
            nome = cpf = sintoma = horario = None
            resposta = "Perfeito. Vamos começar um novo agendamento. Qual é o sintoma ou especialidade?"

        # PAUSA
        elif any(p in msg_lower for p in AGUARDAR_PALAVRAS):
            resposta = "Sem problema, fico no aguardo."

        # TRIAGEM
        elif estado == "TRIAGEM":
            if len(msg.split()) < 2 and msg_lower not in ["dor", "febre", "checkup"]:
                resposta = "Por favor, me explique um pouco mais sobre o sintoma para te direcionar corretamente."
            else:
                sintoma = msg
                esp = detectar_especialidade(sintoma)
                estado = "AGENDAMENTO"
                
                if vagas_lista:
                    resposta = f"Entendi. O ideal é passarmos com um {esp}. Horários disponíveis: {vagas_txt}. Qual prefere?"
                else:
                    estado = "LISTA_ESPERA_DADOS"
                    resposta = f"Entendi. O ideal é o {esp}, mas nossa agenda está cheia. Deseja entrar na lista de espera? (Responda Sim ou Não)"

        # AGENDAMENTO
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            if not match:
                resposta = f"Por favor, digite o número do horário que prefere: {vagas_txt}"
            else:
                h = match.group(1).zfill(2)
                horario_escolhido = next((v for v in vagas_lista if v.startswith(h)), None)

                if not horario_escolhido:
                    resposta = f"Escolha um horário válido: {vagas_txt}"
                else:
                    horario = horario_escolhido
                    estado = "DADOS_NOME"
                    resposta = f"Horário {horario} reservado. Qual o nome completo do paciente?"

        # NOME
        elif estado == "DADOS_NOME":
            if len(msg.split()) < 2:
                resposta = "Por favor, informe o nome e o sobrenome."
            else:
                nome = msg
                estado = "DADOS_CPF"
                resposta = f"Obrigado, {nome.split()[0]}. Envie o CPF do paciente (apenas os 11 números)."

        # CPF E CONCLUSÃO
        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', msg)

            if len(cpf_limpo) != 11:
                resposta = "CPF inválido. Digite os 11 números corretamente."
            else:
                cpf = cpf_limpo
                estado = "CONFIRMADO"

                cur.execute("""
                    UPDATE agenda SET disponivel=FALSE
                    WHERE id IN (
                        SELECT id FROM agenda
                        WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE
                        LIMIT 1
                    )
                """, (f"{horario}%",))

                resposta = f"Consulta confirmada para as {horario}. Aguardamos o paciente!"

        # LISTA DE ESPERA (Tratamento Rápido)
        elif estado == "LISTA_ESPERA_DADOS":
            if "sim" in msg_lower or "quero" in msg_lower:
                estado = "CONFIRMADO"
                resposta = "Você foi adicionado à lista de espera prioritária. Avisaremos assim que surgir vaga."
            else:
                estado = "TRIAGEM"
                nome = cpf = sintoma = horario = None
                resposta = "Compreendo. Se precisar de algo mais, estou à disposição."

        # CONFIRMADO
        elif estado == "CONFIRMADO":
            resposta = "Seu agendamento já está confirmado. Se precisar marcar outra consulta, é só me pedir."

        else:
            estado = "TRIAGEM"
            resposta = "Como posso ajudar você hoje? Qual o sintoma?"

        # SALVAMENTO FINAL
        cur.execute("""
            UPDATE sessoes
            SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s
            WHERE telefone=%s
        """, (estado, nome, cpf, sintoma, horario, msg, telefone))

        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print("Erro Geral Webhook:", e)

    finally:
        if conn:
            conn.close()

    return "OK", 200

# =========================
# RESET
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM agenda;")
    cur.execute("DELETE FROM sessoes;")

    for h in ["09:00", "11:00", "14:30", "16:00"]:
        cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))

    conn.commit()
    conn.close()

    return "✅ RESET V8.1 OK", 200

# =========================
# HOME
# =========================
@app.route('/')
def home():
    return "🚀 IMPÉRIO DE SILÍCIO V8.1 ONLINE", 200

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
