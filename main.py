
import openai, os, json
import urllib.request
from flask import Flask, request

# Configuração da sua "Mente de Elite"
app = Flask(__name__)
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    # 1. Pega TUDO o que a Z-API mandar
    dados = request.get_json(silent=True) or request.form.to_dict()
    print(f"🚨 DADOS RECEBIDOS DA Z-API: {dados}")
    
    # 2. Tenta encontrar o telefone e o texto do cliente
    telefone_cliente = dados.get("phone")
    
    mensagem_cliente = ""
    if "text" in dados and isinstance(dados["text"], dict):
        mensagem_cliente = dados["text"].get("message", "")
    
    from_me = dados.get("fromMe", False)
    
    # Se faltar algum dado importante ou for mensagem sua mesmo, ignora
    if not telefone_cliente or not mensagem_cliente or from_me:
        return "OK", 200
        
    print(f"🤖 MENSAGEM LIDA DE {telefone_cliente}: {mensagem_cliente}")
    
    # 3. O Cérebro: Agente processa a resposta usando IA
    resposta_ia = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Você é o assistente de elite do Império de Silício. Seja altamente profissional e rápido nas respostas."},
            {"role": "user", "content": mensagem_cliente}
        ]
    )
    texto_resposta = resposta_ia.choices[0].message.content
    print(f"✅ RESPOSTA GERADA: {texto_resposta}")

    # 4. A Boca: Envia de volta pro Z-API
    instancia = os.environ.get("ZAPI_INSTANCE_ID")
    token = os.environ.get("ZAPI_TOKEN")
    url_zapi = f"https://api.z-api.io/instances/{instancia}/token/{token}/send-text"

    corpo_envio = json.dumps({"phone": telefone_cliente, "message": texto_resposta}).encode('utf-8')
    req = urllib.request.Request(url_zapi, data=corpo_envio, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req)
        print("🚀 ENVIADO COM SUCESSO PRO WHATSAPP!")
    except Exception as e:
        print(f"❌ ERRO AO ENVIAR PRA Z-API: {e}")

    return "OK", 200

if __name__ == "__main__":
    app.run(port=5000)
