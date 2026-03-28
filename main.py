import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE DE ELITE FINAL - OPERAÇÃO DIAMANTE ATIVA")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# BANCO DE DADOS
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
        print("✅ BANCO SINCRONIZADO")
    except Exception as e:
        print("❌ ERRO BANCO:", e)
    finally:
        if conn: conn.close()

init_db()

# =========================
# AUXILIARES
# =========================
def enviar_whatsapp(telefone, mensagem):
    try:
        requests.post(
            f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
            json={"phone": telefone, "message": mensagem},
            timeout=10
        )
    except Exception as e:
        print("Erro WhatsApp:", e)

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

        # BUSCA VAGAS
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_lista = [v[0] for v in cur.fetchall()]
        vagas = ", ".join(vagas_lista) if vagas_lista else "Agenda cheia"

        resposta = ""

        # LÓGICA DE ATENDIMENTO
        if estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            resposta = f"Entendi sua necessidade. Para esses sintomas, o ideal é o Clínico Geral. Tenho horários: {vagas}. Qual você escolhe?"

        elif estado == "AGENDAMENTO":
            # Pega o primeiro número da mensagem como hora
            match = re.search(r'(\d{1,2})', msg)
            h_dig = match.group(1).zfill(2) if match else ""
            
            h_final = None
            for v in vagas_lista:
                if v.startswith(h_dig): h_final = v
            
            if not h_final:
                resposta = f"Por favor, escolha um destes horários: {vagas}"
            else:
                horario = h_final
                estado = "DADOS_NOME"
                resposta = f"Perfeito, pré-agendado para {horario}. Agora, me informe seu nome completo para a ficha."

        elif estado == "DADOS_NOME":
            nome = msg
            estado = "DADOS_CPF"
            resposta = f"Obrigado, {nome.split()[0]}. Para finalizar, digite apenas os 11 números do seu CPF."

        elif estado == "DADOS_CPF":
            nums = re.sub(r'\D', '', msg)
            if len(nums) != 11:
                resposta = "CPF inválido. Digite os 11 números, por favor."
            else:
                cpf = nums
                estado = "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE hora=%s AND disponivel=TRUE LIMIT 1)", (horario,))
                resposta = f"Tudo pronto! Seu agendamento para {horario} foi confirmado com sucesso. Nossa equipe te aguarda!"

        else:
            resposta = "Seu agendamento já está confirmado. Em breve entraremos em contato."

        # ATUALIZA TUDO E FECHA
        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", 
                   (estado, nome, cpf, sintoma, horario, msg, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print(f"❌ ERRO: {e}")
    finally:
        if conn: conn.close()

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
        cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
        for h in ["09:00", "11:00", "14:30", "16:00"]:
            cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "✅ RESET OK", 200
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 AGENTE ONLINE", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
