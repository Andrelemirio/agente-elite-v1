import openai
from flask import Flask, request

# Configuração da sua "Mente de Elite"
app = Flask(__name__)
# Aqui no futuro colocaremos a tua chave secreta de forma segura
openai.api_key = "SUA_CHAVE_AQUI"

@app.route("/webhook", methods=["POST"])
def webhook():
    # 1. O Agente recebe a mensagem do cliente
    mensagem_cliente = request.values.get('Body', '').lower()
    
    # 2. O Agente processa a resposta usando IA
    resposta_ia = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Você é o assistente de elite do Império de Silício. Seja profissional e direto."},
            {"role": "user", "content": mensagem_cliente}
        ]
    )
    
    texto_resposta = resposta_ia.choices[0].message.content
    
    # 3. Simulação de resposta para o terminal
    print(f"Agente respondeu: {texto_resposta}")
    return texto_resposta

if __name__ == "__main__":
    app.run(port=5000)
