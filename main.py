import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: V6.3 BLINDAGEM DE AÇO - ONLINE")

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
        print("✅ BANCO DE DADOS PROTEGIDO")
    except Exception as e:
        print(f"❌ ERRO BANCO: {e}")
    finally:
        if conn: conn.close()

init_db()

def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
    except Exception as e:
        print(f"Erro WhatsApp: {e}")

# =========================
# WEBHOOK (O MOTOR BLINDADO)
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    print("📩 MENSAGEM DETECTADA NO WEBHOOK!") # Isso vai provar se a Z-API enviou
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200

        telefone = data.get("phone", "").split("@")[0]
        msg = data["text"]["message"] if "text" in data and "message" in data["text"] else data.get("message", "")
        
        if not telefone or not msg: return "OK", 200

        conn = conectar()
        cur = conn.cursor()

        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        sessao = cur.fetchone()

        if not sessao:
            cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, 'TRIAGEM')", (telefone,))
            conn.commit()
            estado, nome, cpf, sintoma, horario, ultima_msg = 'TRIAGEM', None, None, None, None, None
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = sessao

        if msg == ultima_msg: return "OK", 200

        # BUSCA VAGAS
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE AND hora IS NOT NULL ORDER BY hora LIMIT 4")
        vagas_lista = [v[0] for v in cur.fetchall() if v[0] is not None]
        vagas_txt = ", ".join(vagas_lista) if vagas_lista else "Agenda lotada"

        resposta = ""
        if not vagas_lista:
            resposta = "Olá! No momento nossa agenda está completa. Posso te colocar na lista de espera?"
            estado = "TRIAGEM"
        elif estado == "TRIAGEM":
            sintoma, estado = msg, "AGENDAMENTO"
            resposta = f"Entendi. Para esses sintomas, o ideal é o Clínico Geral. Tenho horários: {vagas_txt}. Qual você prefere?"
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            h_dig = match.group(1).zfill(2) if match else ""
            h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
            if not h_final:
                resposta = f"Por favor, escolha um destes horários: {vagas_txt}"
            else:
                horario, estado = h_final, "DADOS_NOME"
                resposta = f"Perfeito, reservado para às {horario}. Qual seu nome completo?"
        elif estado == "DADOS_NOME":
            nome, estado = msg, "DADOS_CPF"
            resposta = f"Obrigado, {msg.split()[0]}. Digite apenas os 11 números do seu CPF."
        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', msg)
            if len(cpf_limpo) != 11:
                resposta = "CPF inválido. Digite os 11 números."
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE hora=%s AND disponivel=TRUE LIMIT 1)", (horario,))
                resposta = f"Confirmado para {horario}. Nossa equipe te aguarda!"
        else:
            resposta = "Seu agendamento já está confirmado."

        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", 
                   (estado, nome, cpf, sintoma, horario, msg, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print(f"❌ ERRO: {e}")
    finally:
        if conn: conn.close()
    return "OK", 200

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
        return "✅ RESET COMPLETO!", 200
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 AGENTE V6.3 ONLINE", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
