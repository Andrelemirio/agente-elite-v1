import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE ELITE V7 - CONTROLE TOTAL ONLINE")

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
            telefone TEXT PRIMARY KEY, estado TEXT, nome TEXT, cpf TEXT, sintoma TEXT, horario TEXT, ultima_msg TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id SERIAL PRIMARY KEY, hora TEXT, disponivel BOOLEAN DEFAULT TRUE
        )
        """)
        conn.commit()
        print("✅ BANCO OK")
    except Exception as e:
        print("❌ ERRO BANCO:", e)
    finally:
        if conn: conn.close()

init_db()

# =========================
# WHATSAPP
# =========================
def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        res = requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
        print("📤 ENVIO WHATS:", res.status_code)
    except Exception as e:
        print("❌ ERRO ENVIO:", e)

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    print("\n📩 NOVA REQUISIÇÃO RECEBIDA DA Z-API!") # SE ISSO NÃO APARECER NO LOG, A Z-API ESTÁ DESCONECTADA
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200

        telefone = data.get("phone", "").split("@")[0]
        msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else data.get("message", "")
        
        if not telefone or not msg: return "OK", 200

        print(f"📞 TEL: {telefone} | 💬 MSG: {msg}")

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
            print("⚠️ MSG DUPLICADA IGNORADA")
            return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE AND hora IS NOT NULL ORDER BY hora LIMIT 4")
        vagas = [v[0] for v in cur.fetchall() if v[0] is not None]
        vagas_txt = ", ".join(vagas) if vagas else "Agenda lotada"

        resposta = ""

        if not vagas:
            resposta = "Nossa agenda lotou. Deseja entrar na lista de espera?"
            estado = "TRIAGEM"
        elif estado == "TRIAGEM":
            sintoma, estado = msg, "AGENDAMENTO"
            resposta = f"Entendi. Para isso, o ideal é o Clínico. Horários disponíveis: {vagas_txt}. Qual prefere?"
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            if not match:
                resposta = f"Escolha um horário válido: {vagas_txt}"
            else:
                h = match.group(1).zfill(2)
                horario = next((v for v in vagas if v.startswith(h)), None)
                if not horario:
                    resposta = f"Escolha um horário válido: {vagas_txt}"
                else:
                    estado, resposta = "NOME", f"Perfeito, {horario} reservado. Qual seu nome completo?"
        elif estado == "NOME":
            nome, estado = msg, "CPF"
            resposta = "Digite seu CPF (11 números)."
        elif estado == "CPF":
            cpf_limpo = re.sub(r'\D', '', msg)
            if len(cpf_limpo) != 11:
                resposta = "CPF inválido. Digite os 11 números."
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE hora=%s AND disponivel=TRUE LIMIT 1)", (horario,))
                resposta = f"Agendamento confirmado para {horario}. Equipe aguardando."
        else:
            resposta = "Seu agendamento já está confirmado."

        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", 
                    (estado, nome, cpf, sintoma, horario, msg, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print("❌ ERRO GERAL:", e)
    finally:
        if conn: conn.close()

    return "OK", 200

# =========================
# RESET
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
def home():
    return "🚀 AGENTE V7 ONLINE", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
