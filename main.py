Import os
import requests
import psycopg2
from flask import Flask, request

app = Flask(__name__)

# ENV
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# =========================
# BANCO DE DADOS
# =========================
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def inicializar_banco():
    try:
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS historico_atendimento (
                id SERIAL PRIMARY KEY,
                telefone VARCHAR(50),
                perfil VARCHAR(20),
                mensagem TEXT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Banco pronto")
    except Exception as e:
        print(f"Erro banco: {e}")

inicializar_banco()

# =========================
# PROMPT ELITE FINAL
# =========================
def gerar_prompt():
    return """
Você é um Especialista em Conversão e Agendamento de uma Clínica Premium.

MISSÃO:
Levar o cliente até o AGENDAMENTO.

REGRAS:
- Nunca peça desculpas
- Nunca reinicie conversa
- Nunca diga "como posso ajudar" após início
- Máximo 2 frases
- Sempre conduzir

COMPORTAMENTO:
- Cliente perdido → faça perguntas diretas
- Emoção → leve para avaliação médica
- Sem dinheiro → ofereça parcelamento
- Brincadeira → ignore e volte ao foco

FLUXO:
1. Sintoma
2. Especialidade
3. Horário
4. Fechamento

EXEMPLOS:

Cliente: "não sei"
Resposta: "Vamos resolver isso agora. O que você está sentindo?"

Cliente: "estou mal emocionalmente"
Resposta: "Isso precisa de avaliação profissional. Vamos agendar hoje. Prefere manhã ou tarde?"

Cliente: "sem dinheiro"
Resposta: "Temos parcelamento. Vamos garantir seu atendimento. Qual horário prefere?"
"""

# =========================
# ROTA PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.get_json(force=True)
    except:
        return "OK", 200

    if not dados or dados.get("fromMe"):
        return "OK", 200

    telefone = dados.get("phone", "").split("@")[0]
    mensagem = ""

    if isinstance(dados.get("text"), dict):
        mensagem = dados["text"].get("message", "")
    elif isinstance(dados.get("text"), str):
        mensagem = dados["text"]
    elif "message" in dados:
        mensagem = dados["message"]

    if not telefone or not mensagem:
        return "OK", 200

    print(f"[{telefone}] Cliente: {mensagem}")

    try:
        conn = conectar_banco()
        cur = conn.cursor()

        # salva cliente
        cur.execute(
            "INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)",
            (telefone, "user", mensagem)
        )
        conn.commit()

        # busca histórico
        cur.execute("""
            SELECT perfil, mensagem FROM (
                SELECT perfil, mensagem, data_hora
                FROM historico_atendimento
                WHERE telefone = %s
                ORDER BY data_hora DESC LIMIT 10
            ) sub ORDER BY data_hora ASC
        """, (telefone,))

        historico = [{"role": "system", "content": gerar_prompt()}]

        for perfil, msg in cur.fetchall():
            role = "assistant" if perfil == "assistant" else "user"
            historico.append({"role": role, "content": msg})

        # OpenAI
        resposta = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": historico,
                "temperature": 0.7
            }
        )

        if resposta.status_code != 200:
            print(resposta.text)
            return "OK", 200

        resposta_texto = resposta.json()['choices'][0]['message']['content']

        # salva resposta
        cur.execute(
            "INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)",
            (telefone, "assistant", resposta_texto)
        )
        conn.commit()

        cur.close()
        conn.close()

        print(f"Robô: {resposta_texto}")

        # envia WhatsApp
        requests.post(
            f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
            headers={
                "Content-Type": "application/json",
                "Client-Token": ZAPI_CLIENT_TOKEN
            },
            json={
                "phone": telefone,
                "message": resposta_texto
            }
        )

    except Exception as e:
        print(f"Erro geral: {e}")

    return "OK", 200


@app.route('/', methods=['GET'])
def home():
    return "Império de Silício rodando 🚀", 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
