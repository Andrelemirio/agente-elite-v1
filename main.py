import os
import requests
from flask import Flask, request

app = Flask(__name__)

OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()

@app.route('/', methods=['GET'])
def home():
    return "Império de Silício Online 🏛️", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    print("🚨 ALERTA: O WEBHOOK FOI ACIONADO!")
    
    try:
        # Pega os dados brutos e força a leitura
        dados = request.get_json(force=True)
        print(f"📦 DADOS DA Z-API: {dados}")
    except Exception as e:
        print(f"❌ ERRO AO LER A MENSAGEM: {e}")
        return "OK", 200

    if not dados: return "OK", 200

    if dados.get("fromMe") is True:
        print("🛑 Mensagem enviada por você mesmo. Ignorada para evitar loop.")
        return "OK", 200

    remote_jid = dados.get("phone", "")
    
    # Tenta pegar o texto de várias formas possíveis
    message_text = ""
    if "text" in dados and isinstance(dados["text"], dict):
        message_text = dados["text"].get("message", "")
    elif "text" in dados and isinstance(dados["text"], str):
         message_text = dados["text"]
    elif "message" in dados:
         message_text = dados["message"]

    clean_phone = remote_jid.split("@")[0] if remote_jid else "Desconhecido"
    print(f"📲 DE: {clean_phone} | MENSAGEM: {message_text}")

    if not message_text:
        print("⚠️ A mensagem não tem texto (pode ser áudio ou imagem). O robô vai ignorar.")
        return "OK", 200

    try:
        print("🧠 Chamando a OpenAI (Agente de Elite)...")
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}"}
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system", 
                    "content": "Você é o Agente de Elite de Atendimento da Clínica. Sua postura é profissional, séria e focada em saúde. Seu objetivo único é converter conversas em agendamentos. Responda de forma curta, em no máximo 3 frases."
                },
                {"role": "user", "content": message_text}
            ]
        }
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        
        if res_ai.status_code != 200:
             print(f"❌ ERRO NA OPENAI: {res_ai.text}")
             return "OK", 200
             
        resposta_ai = res_ai.json()['choices'][0]['message']['content']
        print(f"🗣️ RESPOSTA DO ROBÔ: {resposta_ai}")

        print("🚀 Devolvendo a mensagem para a Z-API...")
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        headers_zapi = {
            "Content-Type": "application/json",
            "Client-Token": ZAPI_CLIENT_TOKEN
        }
        payload_zapi = {
            "phone": clean_phone,
            "message": resposta_ai
        }
        
        envio = requests.post(url_zapi, json=payload_zapi, headers=headers_zapi)
        print(f"✅ STATUS FINAL DA Z-API: {envio.status_code} | {envio.text}")

    except Exception as e:
        print(f"🔥 ERRO FATAL NO PROCESSO: {e}")

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
