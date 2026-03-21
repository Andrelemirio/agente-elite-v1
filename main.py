
import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Pegamos as 4 chaves do Render e limpamos espaços (strip)
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

    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    
    if not remote_jid or not message_text: return "Ignorado", 200

    # Limpa o número (remove @c.us)
    clean_phone = remote_jid.split("@")[0]
    print(f"📩 MENSAGEM DE {clean_phone}: {message_text}")

    try:
        # 1. IA gera a resposta
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}"}
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "Você é o Agente de Elite do Império de Silício. Venda o e-book de R$ 47 de forma curta e direta."},
                {"role": "user", "content": message_text}
            ]
        }
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        resposta_ai = res_ai.json()['choices'][0]['message']['content']
        print(f"🤖 IA RESPONDEU: {resposta_ai}")

        # 2. Envio para Z-API com os Headers CORRETOS
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        
        # AQUI ESTÁ O QUE FALTAVA NO SEU PRINT:
        headers_zapi = {
            "Content-Type": "application/json",
            "Client-Token": ZAPI_CLIENT_TOKEN
        }
        
        payload_zapi = {
            "phone": clean_phone,
            "message": resposta_ai
        }
        
        # Enviando com os headers de segurança
        envio = requests.post(url_zapi, json=payload_zapi, headers=headers_zapi)
        
        if envio.status_code in [200, 201]:
            print(f"✅ SUCESSO: Enviado para {clean_phone}")
        else:
            print(f"❌ ERRO Z-API ({envio.status_code}): {envio.text}")

    except Exception as e:
        print(f"⚠️ ERRO GERAL: {e}")

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
