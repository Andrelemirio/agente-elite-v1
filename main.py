import os, requests, sqlite3, json
from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

# Configurações de Ambiente
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT msg_cliente, msg_ia FROM historico WHERE telefone = ? ORDER BY id DESC LIMIT 4", (telefone,))
    rows = cursor.fetchall()
    conn.close()
    return "\n".join([f"Paciente: {r[0]}\nAgente: {r[1]}" for r in reversed(rows)])

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

    # 🚨 FILTRO DE ELITE: Só responde se for uma mensagem recebida e se tiver texto
    # Isso evita as respostas duplas e o consumo desnecessário de créditos
    if dados.get("type") != "ReceivedMessage" or "text" not in dados:
        return "Evento ignorado", 200

    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    
    # Ignora mensagens enviadas pelo próprio robô
    if not remote_jid or not message_text or dados.get("fromMe", False): 
        return "Ignorado", 200

    clean_phone = remote_jid.split("@")[0]
    memoria = buscar_memoria(clean_phone)

    try:
        # 🧠 IA COM PERSONALIDADE DE FERRO: Focada 100% em Saúde e Agendamento
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
        prompt_sistema = (
            "Você é o Especialista de Elite da Clínica de Saúde. "
            "Sua missão única é cuidar da saúde dos pacientes e agendar consultas. "
            "REGRAS CRÍTICAS:\n"
            "1. RESPONDA TUDO EM APENAS UM PARÁGRAFO CURTO.\n"
            "2. Nunca peça ou empreste dinheiro. Se o assunto fugir de saúde, diga que seu foco é o bem-estar médico e tente voltar para o agendamento.\n"
            "3. Se o paciente estiver confuso, acolha-o e mostre autoridade médica.\n"
            f"HISTÓRICO:\n{memoria}"
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

        salvar_conversa(clean_phone, message_text, resposta_ai)

        # Envio Blindado
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
