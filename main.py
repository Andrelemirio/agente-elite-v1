
import os, requests, sqlite3, json
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

# Configurações de Ambiente (Segurança Máxima)
OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()
DB_NAME = "agente_elite.db"

# 1. FUNDAMENTO: Inicializa o Banco de Dados SQL
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, telefone TEXT, cliente_msg TEXT, ia_resp TEXT, data TIMESTAMP)''')
    conn.commit()
    conn.close()

# 2. MEMÓRIA: Busca o histórico para dar contexto à IA
def buscar_historico(telefone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT cliente_msg, ia_resp FROM historico WHERE telefone = ? ORDER BY id DESC LIMIT 4", (telefone,))
    rows = cursor.fetchall()
    conn.close()
    return "\n".join([f"Cliente: {r[0]}\nAgente: {r[1]}" for r in reversed(rows)])

# 3. REGISTRO: Salva a conversa para a próxima interação
def salvar_conversa(telefone, msg, resp):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO historico (telefone, cliente_msg, ia_resp, data) VALUES (?, ?, ?, ?)",
                   (telefone, msg, resp, datetime.now()))
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET'])
def home():
    return "O Império de Silício está Online! 🏛️🤖", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json()
    if not dados: return "Sem dados", 200

    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    if not remote_jid or not message_text: return "Ignorado", 200

    clean_phone = remote_jid.split("@")[0]
    historico = buscar_historico(clean_phone)

    try:
        # 1. IA com Personalidade de Elite para Clínicas
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
        prompt_sistema = (
            "Você é o Agente de Elite da Clínica. Seu objetivo é agendar consultas de forma persuasiva. "
            "Seja acolhedor, autoritário e contorne objeções com foco em saúde e bem-estar. "
            f"\nHistórico recente:\n{historico}"
        )
        
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": message_text}
            ]
        }
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        resposta_ai = res_ai.json()['choices'][0]['message']['content']

        # 2. Salva na Memória SQL
        salvar_conversa(clean_phone, message_text, resposta_ai)

        # 3. Envio Blindado para Z-API
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        headers_zapi = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
        payload_zapi = {"phone": clean_phone, "message": resposta_ai}
        
        requests.post(url_zapi, json=payload_zapi, headers=headers_zapi)
        print(f"✅ SUCESSO: Respondido para {clean_phone}")

    except Exception as e:
        print(f"⚠️ ERRO GERAL: {e}")

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
