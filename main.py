import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Configurações do Render (Limpando as chaves)
OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()

@app.route('/', methods=['GET'])
def home():
    # Isso aqui resolve o erro de "No open HTTP ports" no Render
    return "Império de Silício Online 🏛️", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json()
    if not dados: return "Sem dados", 200

    # 1. TRAVA ANTI-LOOP (Essencial para não duplicar e não gastar dinheiro à toa)
    if dados.get("fromMe") is True:
        return "Mensagem do próprio bot ignorada", 200

    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    
    if not remote_jid or not message_text: 
        return "Mensagem vazia", 200

    clean_phone = remote_jid.split("@")[0]
    print(f"📩 Nova mensagem de {clean_phone}: {message_text}")

    try:
        # 2. IA com POSTURA DE ESPECIALISTA EM CLÍNICA
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}"}
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system", 
                    "content": (
                        "Você é o Agente de Elite da Clínica. Sua postura é séria, profissional e focada em saúde. "
                        "Sua única missão é levar o cliente ao agendamento. "
                        "Se o cliente fugir do assunto, diga: 'Entendo, mas meu foco aqui é sua saúde. Como posso ajudar com sua consulta?' "
                        "Responda sempre em no máximo 3 frases curtas."
                    )
                },
                {"role": "user", "content": message_text}
            ]
        }
        
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        resposta_ai = res_ai.json()['choices'][0]['message']['content']

        # 3. ENVIO PARA Z-API
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
        print(f"✅ Respondido para {clean_phone}")

    except Exception as e:
        print(f"⚠️ Erro no processamento: {e}")

    return "OK", 200

if __name__ == '__main__':
    # Garante que vai rodar na porta que o Render pedir
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
