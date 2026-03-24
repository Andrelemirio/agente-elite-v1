
import os, requests, sqlite3, json
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

# Configurações do ambiente
OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()
DB_NAME = "clinica_elite.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS historico 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, telefone TEXT, msg_cliente TEXT, msg_ia TEXT, data TIMESTAMP)''')
    conn.commit()
    conn.close()

def buscar_memoria(telefone):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT msg_cliente, msg_ia FROM historico WHERE telefone = ? ORDER BY id DESC LIMIT 3", (telefone,))
        rows = cursor.fetchall()
        conn.close()
        return "\n".join([f"Paciente: {r[0]}\nAgente: {r[1]}" for r in reversed(rows)])
    except: return ""

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

    # --- FILTRO ANT-ERRO (CRUCIAL) ---
    # 1. Ignora se a mensagem foi enviada pelo próprio robô
    if dados.get("fromMe") is True:
        return "Ignorado: Mensagem própria", 200
    
    # 2. Ignora status de leitura ou entrega (só aceita mensagens recebidas)
    # Na Z-API, mensagens reais costumam vir com o campo "isGroup": false (se for privado)
    if dados.get("type") and dados.get("type") != "ReceivedMessage":
        return "Ignorado: Não é uma mensagem recebida", 200

    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    
    if not remote_jid or not message_text:
        return "Ignorado: Sem texto", 200

    clean_phone = remote_jid.split("@")[0]
    memoria = buscar_memoria(clean_phone)

    try:
        # --- PERSONAGEM DE ELITE (PROMPT REFORÇADO) ---
        prompt_sistema = (
            "VOCÊ É O AGENTE DE ELITE DA CLÍNICA. SUA POSTURA É INABALÁVEL.\n"
            "REGRAS CRÍTICAS:\n"
            "1. Você NUNCA fala de ganhar dinheiro ou assuntos fora da clínica.\n"
            "2. Se o paciente desviar o assunto, responda: 'Entendo, mas meu foco é sua saúde. Como posso ajudar com seu agendamento?'\n"
            "3. Seja empático, mas direto ao ponto. Sua meta é o agendamento.\n"
            "4. Responda em no máximo 3 frases curtas.\n"
            f"HISTÓRICO RECENTE:\n{memoria}"
        )
        
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": message_text}
            ],
            "temperature": 0.5 # Deixa a IA mais focada e menos 'criativa'
        }
        
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        resposta_ai = res_ai.json()['choices'][0]['message']['content']

        # Envio para Z-API
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        headers_zapi = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
        payload_zapi = {"phone": clean_phone, "message": resposta_ai}
        
        requests.post(url_zapi, json=payload_zapi, headers=headers_zapi)
        
        # Salva na memória DEPOIS de enviar com sucesso
        salvar_conversa(clean_phone, message_text, resposta_ai)

    except Exception as e:
        print(f"⚠️ ERRO: {e}")

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
