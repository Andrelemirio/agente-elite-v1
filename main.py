
import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Pegamos as 4 chaves do Render
OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()

@app.route('/', methods=['GET'])
def home():
    return "O Império de Silício está Online! 🏛️🤖", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json()
    if not dados: return "Sem dados", 200

    # SEGURANÇA: Ignora mensagens que o próprio robô envia
    if dados.get("fromMe") is True:
        return "Ignorado", 200

    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    
    if not remote_jid or not message_text: return "Ignorado", 200

    clean_phone = remote_jid.split("@")[0]

    try:
        # 1. IA com POSTURA DE ELITE (Especialista em Clínica)
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}"}
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system", 
                    "content": (
                        "Você é o Agente de Elite de Atendimento da Clínica. "
                        "Sua postura é profissional, séria e focada em saúde. "
                        "Seu objetivo único é converter conversas em agendamentos. "
                        "Se o cliente falar de assuntos fora de contexto (como ganhar dinheiro), "
                        "reboque a conversa de volta para a saúde com educação e autoridade. "
                        "Responda de forma curta, em no máximo 3 frases."
                    )
                },
                {"role": "user", "content": message_text}
            ]
        }
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        resposta_ai = res_ai.json()['choices'][0]['message']['content']

        # 2. Envio ÚNICO para Z-API
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        headers_zapi = {
            "Content-Type": "application/json",
            "Client-Token": ZAPI_CLIENT_TOKEN
        }
        payload_zapi = {
            "phone": clean_phone,
            "message": resposta_ai
        }
        
        requests.post(url_zapi, json=payload_zapi, headers=headers_zapi)

    except Exception as e:
        print(f"Erro: {e}")

    return "OK", 200

# AQUI ESTÁ A CORREÇÃO DA PORTA QUE O RENDER PRECISA:
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
