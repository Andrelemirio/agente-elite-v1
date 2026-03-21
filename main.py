

    
    import os
import json
import openai
import urllib.request
from flask import Flask, request

app = Flask(__name__)

# Configurações via Variáveis de Ambiente no Render
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")

# Configuração da chave para a versão que você tem instalada
openai.api_key = OPENAI_KEY

@app.route('/', methods=['GET'])
def home():
    return "O Império de Silício está Online! 🏛️🤖", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json()
    if not dados:
        return "Sem dados", 200

    # Pega o número e limpa para evitar Erro 400
    remote_jid = dados.get("phone", "")
    message_text = dados.get("text", {}).get("message", "")
    is_group = dados.get("isGroup", False)
    
    # --- LIMPEZA DO NÚMERO ---
    clean_phone = remote_jid.split("@")[0]

    if is_group or not message_text:
        return "Ignorado", 200

    print(f"📩 MENSAGEM LIDA DE {clean_phone}: {message_text}")

    try:
        # Chamada usando a sintaxe compatível com seu ambiente atual
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é o Agente de Elite do Império de Silício. Responda de forma curta, direta e persuasiva, focada em vender o e-book de R$ 47 sobre IA."},
                {"role": "user", "content": message_text}
            ]
        )
        resposta_ai = response.choices[0].message.content

        # Enviar a resposta via Z-API usando urllib (mais estável no seu caso)
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        corpo_envio = json.dumps({
            "phone": clean_phone,
            "message": resposta_ai
        }).encode('utf-8')
        
        req = urllib.request.Request(url_zapi, data=corpo_envio, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response_zapi:
            if response_zapi.getcode() in [200, 201]:
                print(f"✅ RESPOSTA ENVIADA PARA {clean_phone}")

    except Exception as e:
        print(f"⚠️ ERRO NO PROCESSAMENTO: {e}")

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
