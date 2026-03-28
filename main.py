import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE DE ELITE FINAL - CONTROLE TOTAL ATIVO")

app = Flask(__name__)

# =========================
# CONFIG
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# BANCO
# =========================
def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

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
        print("✅ BANCO PRONTO E CONECTADO")
    except Exception as e:
        print("❌ ERRO BANCO:", e)
    finally:
        if conn:
            conn.close()

init_db()

# =========================
# AUXILIARES
# =========================
def detectar_horario(msg):
    match = re.search(r'\b(0?[0-9]|1[0-9]|2[0-3])\b', msg)
    return match.group() if match else None

def validar_cpf(cpf):
    nums = re.sub(r'\D', '', cpf)
    return len(nums) == 11

def enviar_whatsapp(telefone, mensagem):
    try:
        requests.post(
            f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
            json={"phone": telefone, "message": mensagem},
            timeout=10
        )
    except Exception as e:
        print("Erro envio WhatsApp:", e)

# =========================
# WEBHOOK (REVISADO)
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200

        telefone = data.get("phone", "").split("@")[0]
        msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else data.get("message", "")
        if not telefone or not msg: return "OK", 200

        conn = conectar()
        cur = conn.cursor()

        # BUSCA SESSÃO
        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        sessao = cur.fetchone()

        if not sessao:
            cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, 'TRIAGEM')", (telefone,))
            conn.commit()
            estado, nome, cpf, sintoma, horario, ultima_msg = 'TRIAGEM', None, None, None, None, None
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = sessao

        # ANTI DUPLICAÇÃO
        if msg == ultima_msg:
            return "OK", 200

        cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg, telefone))
        conn.commit()

        # BUSCA VAGAS
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_lista = [v[0] for v in cur.fetchall()]
        vagas = ", ".join(vagas_lista) if vagas_lista else "Agenda cheia"

        resposta = ""

        # MOTOR DE ESTADOS
        if estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            resposta = f"Entendi. Para esses sintomas, o ideal é o clínico. Tenho horários: {vagas}. Qual você escolhe?"

        elif estado == "AGENDAMENTO":
            h_det = detectar_horario(msg)
            if not h_det:
                resposta = f"Por favor, escolha um horário válido: {vagas}"
            else:
                # Ajuste para bater com o formato do banco (ex: 09:00)
                horario = f"{h_det.zfill(2)}:00"
                if horario not in vagas:
                    # Tenta ver se é meia hora (ex: 14:30)
                    horario = f"{h_det.zfill(2)}:30"
                
                if horario not in vagas:
                    resposta = f"Esse horário não está disponível. Escolha entre: {vagas}"
                else:
                    estado = "DADOS_NOME"
                    resposta = f"Perfeito, agendado para às {horario}. Agora, me informe seu nome completo."

        elif estado == "DADOS_NOME":
            nome = msg
            estado = "DADOS_CPF"
            resposta = "Obrigado. Agora preciso do seu CPF (apenas os 11 números)."

        elif estado == "DADOS_CPF":
            if not validar_cpf(msg):
                resposta = "CPF inválido. Digite os 11 números, por favor."
            else:
                cpf = re.sub(r'\D', '', msg)
                estado = "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE hora=%s AND disponivel=TRUE LIMIT 1)", (horario,))
                resposta = f"Agendamento confirmado para {horario}. Nossa equipe te aguarda!"

        else:
            resposta = "Seu agendamento já está confirmado. Em breve nossa equipe entrará em contato."

        # ATUALIZA TUDO
        cur.execute("""
            UPDATE sessoes 
            SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s 
            WHERE telefone=%s
        """, (estado, nome, cpf, sintoma, horario, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print(f"❌ ERRO NO PROCESSO: {e}")
    finally:
        if conn:
            conn.close() # ESSA LINHA IMPEDE O TRAVAMENTO

    return "OK", 200

# =========================
# RESET E HOME
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM agenda")
        cur.execute("DELETE FROM sessoes")
        for h in ["08:00", "09:30", "11:00", "14:30", "16:00"]:
            cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "RESET OK", 200
    finally:
        if conn: conn.close()

@app.route('/')
def home():
    return "🚀 AGENTE DE ELITE FINAL ONLINE", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
