import os
import requests
import psycopg2
from flask import Flask, request

app = Flask(__name__)

# Pegando as chaves do Render
OPENAI_KEY = str(os.environ.get("OPENAI_API_KEY", "")).strip()
ZAPI_INSTANCE = str(os.environ.get("ZAPI_INSTANCE_ID", "")).strip()
ZAPI_TOKEN = str(os.environ.get("ZAPI_TOKEN", "")).strip()
ZAPI_CLIENT_TOKEN = str(os.environ.get("ZAPI_CLIENT_TOKEN", "")).strip()
DATABASE_URL = str(os.environ.get("DATABASE_URL", "")).strip()

# Função para conectar ao Banco de Dados PostgreSQL (Com trava de segurança SSL)
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# Criar a estrutura do banco automaticamente se não existir
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
        print("🏛️ Banco de Dados PostgreSQL Inicializado e Blindado!")
    except Exception as e:
        print(f"❌ Erro ao inicializar o banco: {e}")

# Roda a inicialização quando o app sobe
inicializar_banco()

@app.route('/', methods=['GET'])
def home():
    return "Império de Silício Online com Banco de Dados! 🏛️🐘", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        dados = request.get_json(force=True)
    except Exception:
        return "OK", 200

    if not dados or dados.get("fromMe") is True:
        return "OK", 200

    remote_jid = dados.get("phone", "")
    message_text = ""
    if "text" in dados and isinstance(dados["text"], dict):
        message_text = dados["text"].get("message", "")
    elif "text" in dados and isinstance(dados["text"], str):
         message_text = dados["text"]
    elif "message" in dados:
         message_text = dados["message"]

    if not remote_jid or not message_text:
        return "OK", 200

    clean_phone = remote_jid.split("@")[0]
    print(f"📩 [{clean_phone}] Cliente: {message_text}")

    # 1. Salvar a mensagem do cliente no Banco de Dados
    try:
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", 
                    (clean_phone, "user", message_text))
        conn.commit()
    except Exception as e:
        print(f"🔥 Erro ao salvar cliente no BD: {e}")
        return "OK", 200

    # 2. Resgatar as últimas 10 interações para o Cérebro da IA ler
    historico_openai = []
    
    # O SCRIPT DE ELITE BLINDADO
    prompt_sistema = (
        # O SCRIPT DE ELITE BLINDADO - MODO FECHAMENTO
    prompt_sistema = (
        # O SCRIPT DE ELITE BLINDADO
    prompt_sistema = (
        Prompt_sistema = (
"Você é um Especialista em Conversão e Agendamento de uma Clínica Premium. "
"Sua única missão é conduzir o cliente até o AGENDAMENTO da consulta com firmeza e controle total da conversa. "

"REGRAS ABSOLUTAS: "
"1. Nunca peça desculpas. Nunca use: desculpa, perdão, sinto muito ou lamento. "
"2. Nunca reinicie a conversa. Nunca diga 'como posso ajudar' após já ter iniciado. "
"3. Você lidera sempre. O cliente nunca controla a conversa. "
"4. Respostas curtas, diretas e com objetivo. Máximo 2 frases. "
"5. Sempre conduza para o próximo passo (sintoma → especialidade → horário → agendamento). "

"COMPORTAMENTO: "
"- Se o cliente estiver perdido: conduza com perguntas objetivas. "
"- Se fugir do assunto: ignore e traga de volta para consulta. "
"- Se falar de emoção: direcione para avaliação médica. "
"- Se disser que não tem dinheiro: ofereça parcelamento e continue o fluxo. "
"- Nunca dê respostas genéricas. Sempre direcione. "

"FLUXO DE CONVERSÃO: "
"1. Identificar o problema (sintoma) "
"2. Direcionar especialidade "
"3. Oferecer horário específico "
"4. Fechar agendamento "

"EXEMPLO DE POSTURA: "
"Cliente: 'não sei o que tenho' "
"Resposta: 'Vamos identificar isso agora. O que você está sentindo exatamente?' "

"Cliente: 'estou mal emocionalmente' "
"Resposta: 'Isso precisa de avaliação profissional. Vamos agendar para você ser atendido ainda hoje. Qual período prefere: manhã ou tarde?' "

"Cliente: 'estou sem dinheiro' "
"Resposta: 'Entendo. Temos parcelamento disponível. Vamos garantir seu atendimento. Qual o melhor horário para você?' "
)


Vou tentar usar este prompt, pois o robo ainda exta fraco
    )
    )
    )
    historico_openai.append({"role": "system", "content": prompt_sistema})

    try:
        # Puxa o histórico organizando do mais antigo para o mais novo
        cur.execute('''
            SELECT perfil, mensagem FROM (
                SELECT perfil, mensagem, data_hora 
                FROM historico_atendimento 
                WHERE telefone = %s 
                ORDER BY data_hora DESC LIMIT 10
            ) sub ORDER BY data_hora ASC
        ''', (clean_phone,))
        
        linhas = cur.fetchall()
        for linha in linhas:
            historico_openai.append({"role": linha[0], "content": linha[1]})
    except Exception as e:
        print(f"🔥 Erro ao buscar histórico: {e}")

    # 3. Processar na OpenAI
    try:
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}"}
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": historico_openai
        }
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        
        if res_ai.status_code == 200:
            resposta_ai = res_ai.json()['choices'][0]['message']['content']

            # 4. Salvar a resposta do Robô no Banco de Dados (Memória)
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", 
                        (clean_phone, "assistant", resposta_ai))
            conn.commit()
            cur.close()
            conn.close()
            print(f"🗣️ Robô: {resposta_ai}")

            # 5. Devolver para o WhatsApp via Z-API
            url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
            headers_zapi = {
                "Content-Type": "application/json",
                "Client-Token": ZAPI_CLIENT_TOKEN
            }
            requests.post(url_zapi, json={"phone": clean_phone, "message": resposta_ai}, headers=headers_zapi)
        else:
            print(f"❌ Erro OpenAI: {res_ai.text}")

    except Exception as e:
        print(f"🔥 Erro OpenAI/Z-API: {e}")

    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
