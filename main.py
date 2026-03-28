import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: V6.0 RESGATE TOTAL - ONLINE")

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

def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        # Cria as tabelas básicas
        cur.execute("CREATE TABLE IF NOT EXISTS sessoes (telefone TEXT PRIMARY KEY, estado TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS agenda (id SERIAL PRIMARY KEY, hora TEXT, disponivel BOOLEAN DEFAULT TRUE)")
        
        # FORÇA A ATUALIZAÇÃO DAS COLUNAS (O SEGREDO DO RESGATE)
        colunas = ["nome", "cpf", "sintoma", "horario", "ultima_msg"]
        for col in colunas:
            cur.execute(f"ALTER TABLE sessoes ADD COLUMN IF NOT EXISTS {col} TEXT")
        
        conn.commit()
        print("✅ BANCO DE DADOS ATUALIZADO E PRONTO")
    except Exception as e:
        print(f"❌ ERRO AO INICIAR BANCO: {e}")
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
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        # LOG PARA VOCÊ VER NO RENDER SE A MENSAGEM CHEGOU
        print(f"📩 Recebido: {data}")
        
        if not data or data.get("fromMe"): return "OK", 200

        telefone = data.get("phone", "").split("@")[0]
        # Pega a mensagem de qualquer jeito (Simples ou Full JSON)
        msg = ""
        if "text" in data and isinstance(data["text"], dict):
            msg = data["text"].get("message", "")
        else:
            msg = data.get("message", "")
        
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

        # Evita responder a mesma coisa
        if msg == ultima_msg: return "OK", 200

        # Vagas
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_lista = [v[0] for v in cur.fetchall()]
        vagas_txt = ", ".join(vagas_lista) if vagas_lista else "Agenda cheia"

        resposta = ""
        if estado == "TRIAGEM":
            sintoma, estado = msg, "AGENDAMENTO"
            resposta = f"Olá! Entendi sua necessidade. Para esses sintomas, o ideal é o Clínico Geral. Tenho estes horários: {vagas_txt}. Qual você prefere?"
        
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            h_dig = match.group(1).zfill(2) if match else ""
            h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
            
            if not h_final:
                resposta = f"Por favor, escolha um destes horários: {vagas_txt}"
            else:
                horario, estado = h_final, "DADOS_NOME"
                resposta = f"Perfeito, reservado para às {horario}. Qual seu nome completo para a ficha?"
        
        elif estado == "DADOS_NOME":
            nome, estado = msg, "DADOS_CPF"
            resposta = f"Obrigado, {nome.split()[0]}. Agora digite apenas os 11 números do seu CPF."
            
        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', msg)
            if len(cpf_limpo) != 11:
                resposta = "CPF inválido. Digite os 11 números, por favor."
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE hora=%s AND disponivel=TRUE LIMIT 1)", (horario,))
                resposta = f"Tudo pronto! Seu agendamento para {horario} foi confirmado. Nossa equipe te aguarda!"
        else:
            resposta = "Seu agendamento já está confirmado. Caso precise mudar algo, avise-nos."

        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", 
                   (estado, nome, cpf, sintoma, horario, msg, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print(f"❌ ERRO NO PROCESSO: {e}")
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
        for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "RESET OK", 200
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 AGENTE ONLINE V6.0", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
