
import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# Configurações via Variáveis de Ambiente no Render
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")

client = OpenAI(api_key=OPENAI_KEY)

@app.route('/', methods=['GET'])
def home():
    return "O Império de Silício está Online! 🏛️🤖", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json()
    
    # Verifica se é uma mensagem recebida
    if not dados:
        return "Sem dados", 200

    # Pega o número e o texto da mensagem
    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    is_group = dados.get("isGroup", False)
    
    # --- AJUSTE DE SÓCIO: LIMPEZA DO NÚMERO ---
    # Remove o @c.us ou @s.whatsapp.net para evitar Erro 400 na Z-API
    clean_phone = remote_jid.split("@")[0]

    # Se for grupo ou mensagem vazia, ignora
    if is_group or not message_text:
        return "Ignorado", 200

    print(f"📩 MENSAGEM LIDA DE {clean_phone}: {message_text}")

    try:
        # 1. Chamar o Cérebro (OpenAI)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é o Agente de Elite do Império de Silício. Responda de forma curta, direta e persuasiva, focada em ajudar o cliente e vender o e-book de R$ 47 sobre IA."},
                {"role": "user", "content": message_text}
            ]
        )
        resposta_ai = response.choices[0].message.content

        # 2. Enviar a resposta via Z-API
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        payload = {
            "phone": clean_phone,
            "message": resposta_ai
        }
        
        headers = {
            "Content-Type": "application/json"
        }

        envio = requests.post(url_zapi, json=payload, headers=headers)
        
        if envio.status_code == 200 or envio.status_code == 201:
            print(f"✅ RESPOSTA ENVIADA PARA {clean_phone}")
        else:
            print(f"❌ ERRO Z-API ({envio.status_code}): {envio.text}")

    except Exception as e:
        print(f"⚠️ ERRO NO PROCESSAMENTO: {e}")

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
