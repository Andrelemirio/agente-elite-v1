
import os, requests, sqlite3, json
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

# Pegamos as 4 chaves do Render (Garantindo que estão limpas)
OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()
DB_NAME = "clinica_elite.db"

# 1. Banco de Dados SQL (O Fundamento da Memória)
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, telefone TEXT, msg_cliente TEXT, msg_ia TEXT, data TIMESTAMP)''')
    conn.commit()
    conn.close()

# 2. Busca o que foi conversado antes
def buscar_memoria(telefone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT msg_cliente, msg_ia FROM historico WHERE telefone = ? ORDER BY id DESC LIMIT 4", (telefone,))
    rows = cursor.fetchall()
    conn.close()
    return "\n".join([f"Paciente: {r[0]}\nAgente: {r[1]}" for r in reversed(rows)])

# 3. Salva a conversa atual
def salvar_conversa(telefone, msg, resp):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO historico (telefone, msg_cliente, msg_ia, data) VALUES (?, ?, ?, ?)",
                   (telefone, msg, resp, datetime.now()))
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET'])
def home():
    return "Império de Silício Online! 🏛️🤖", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json()
    if not dados: return "Sem dados", 200

    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    
    # Ignora mensagens vazias ou enviadas pelo próprio robô
    if not remote_jid or not message_text or dados.get("fromMe", False): 
        return "Ignorado", 200

    clean_phone = remote_jid.split("@")[0]
    memoria = buscar_memoria(clean_phone)

    try:
        # 1. IA com Personalidade de Elite e Memória
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
        prompt_sistema = (
            "Você é o Especialista de Elite da Clínica. Seu objetivo é agendar consultas de forma persuasiva e acolhedora. "
            f"\nHistórico recente:\n{memoria}"
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

        # 2. Registra no Banco SQL
        salvar_conversa(clean_phone, message_text, resposta_ai)

        # 3. Envio Blindado para Z-API (Usando seu Client-Token)
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
