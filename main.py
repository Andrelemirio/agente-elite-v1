Import os
import requests
import psycopg2
from flask import Flask, request

app = Flask(__name__)

# ENV
OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()
DATABASE_URL = str(os.environ.get("DATABASE_URL", "")).strip()

# DB
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
        print("🏛️ Banco pronto!")
    except Exception as e:
        print(f"Erro banco: {e}")

inicializar_banco()

@app.route('/', methods=['GET'])
def home():
    return "Império de Silício rodando 🚀", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.get_json(force=True)
    except:
        return "OK", 200

    if not dados or dados.get("fromMe") is True:
        return "OK", 200

    remote_jid = dados.get("phone", "")
    message_text = ""

    if isinstance(dados.get("text"), dict):
        message_text = dados["text"].get("message", "")
    elif isinstance(dados.get("text"), str):
        message_text = dados["text"]
    elif "message" in dados:
        message_text = dados["message"]

    if not remote_jid or not message_text:
        return "OK", 200

    clean_phone = remote_jid.split("@")[0]
    print(f"[{clean_phone}] {message_text}")

    # SALVA MENSAGEM USUÁRIO
    try:
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s,%s,%s)",
            (clean_phone, "user", message_text)
        )
        conn.commit()
    except Exception as e:
        print(f"Erro salvar user: {e}")
        return "OK", 200

    # PROMPT DE ELITE
    prompt_sistema = (
        "Você é um Especialista em Conversão de uma Clínica Premium.\n"
        "Missão: AGENDAR CONSULTA.\n"

        "REGRAS:\n"
        "- Nunca peça desculpas\n"
        "- Nunca reinicie conversa\n"
        "- Nunca saia do contexto\n"
        "- Máximo 2 frases\n"

        "COMPORTAMENTO:\n"
        "- Sempre conduza\n"
        "- Sempre puxe para agendamento\n"
        "- Controle total da conversa\n"

        "OBJEÇÕES:\n"
        "Sem dinheiro: 'Temos parcelamento. Vamos garantir seu atendimento.'\n"

        "DESVIO:\n"
        "Ignorar e voltar para consulta.\n"
    )

    historico_openai = [{"role": "system", "content": prompt_sistema}]

    # BUSCA MEMÓRIA
    try:
        cur.execute('''
            SELECT perfil, mensagem FROM (
                SELECT perfil, mensagem, data_hora
                FROM historico_atendimento
                WHERE telefone = %s
                ORDER BY data_hora DESC LIMIT 10
            ) sub ORDER BY data_hora ASC
        ''', (clean_phone,))

        for perfil, msg in cur.fetchall():
            role = "user" if perfil == "user" else "assistant"
            historico_openai.append({"role": role, "content": msg})

    except Exception as e:
        print(f"Erro histórico: {e}")

    # ANTI-DESVIO
    msg_lower = message_text.lower()

    if "kkk" in msg_lower or "brincadeira" in msg_lower:
        resposta_ai = "Vamos focar na sua saúde. Qual sintoma você quer avaliar?"
    elif "triste" in msg_lower or "mal" in msg_lower:
        resposta_ai = "Isso precisa de avaliação profissional. Vamos agendar sua consulta?"
    else:
        try:
            headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": historico_openai
            }

            res = requests.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers
            )

            if res.status_code == 200:
                resposta_ai = res.json()['choices'][0]['message']['content']
            else:
                print("Erro OpenAI:", res.text)
                return "OK", 200

        except Exception as e:
            print("Erro IA:", e)
            return "OK", 200

    # SALVA RESPOSTA
    try:
        cur.execute(
            "INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s,%s,%s)",
            (clean_phone, "assistant", resposta_ai)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Erro salvar bot:", e)

    print("BOT:", resposta_ai)

    # ENVIA WHATSAPP
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"

        headers = {
            "Content-Type": "application/json",
            "Client-Token": ZAPI_CLIENT_TOKEN
        }

        requests.post(url, json={
            "phone": clean_phone,
            "message": resposta_ai
        }, headers=headers)

    except Exception as e:
        print("Erro ZAPI:", e)

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
