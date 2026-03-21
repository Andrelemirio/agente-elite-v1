
import openai, os
import urllib.request, json
from flask import Flask, request

# Configuração da sua "Mente de Elite"
app = Flask(__name__)
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/webhook", methods=["POST"])
def webhook():
    # 1. O Agente recebe os dados no formato exato da Z-API
    dados = request.get_json(silent=True)

    # Se não tiver dados ou telefone, ele ignora silenciosamente
    if not dados or "phone" not in dados:
        return "OK", 200

    # Filtra para não ficar respondendo a si mesmo e garante que é uma mensagem de texto
    if not dados.get("fromMe", False) and "text" in dados:
        mensagem_cliente = dados["text"]["message"]
        telefone_cliente = dados["phone"]

        # 2. O Cérebro: Agente processa a resposta usando IA
        resposta_ia = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é o assistente de elite do Império de Silício. Seja extremamente profissional e resolutivo."},
                {"role": "user", "content": mensagem_cliente}
            ]
        )
        texto_resposta = resposta_ia.choices[0].message.content
        
        # Mostra no Log do Render para o CEO acompanhar
        print(f"Respondendo para {telefone_cliente}: {texto_resposta}")

        # 3. A BOCA: Envia a resposta de volta para o WhatsApp do cliente via Z-API
        instancia = os.environ.get("ZAPI_INSTANCE_ID")
        token = os.environ.get("ZAPI_TOKEN")
        url_zapi = f"https://api.z-api.io/instances/{instancia}/token/{token}/send-text"

        corpo_envio = json.dumps({
            "phone": telefone_cliente, 
            "message": texto_resposta
        }).encode('utf-8')
        
        req = urllib.request.Request(url_zapi, data=corpo_envio, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)

    return "OK", 200

if __name__ == "__main__":
    app.run(port=5000)
