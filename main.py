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
        "Você é o Agente de Vendas de Elite de uma Clínica Médica Premium. "
        "Sua única missão é AGENDAR CONSULTAS e não perder NENHUM negócio. "
        "REGRAS ABSOLUTAS: "
        "1. PROIBIDO PEDIR DESCULPAS: Nunca diga 'peço desculpas', 'sinto muito', 'lamento' ou 'desculpe a confusão'. Um especialista lidera, não se desculpa. "
        "2. POSTURA DE AUTORIDADE: Você controla a conversa. Se o cliente mudar de assunto ou for irônico, corte a distração e puxe de volta para a saúde dele. "
        "3. CONTORNO DE OBJEÇÃO (SEM DINHEIRO): Se o cliente disser que está 'quebrado', 'sem grana' ou 'caro', NUNCA mande ele para outra clínica. Responda: 'A sua saúde é o seu maior ativo, [Nome]. Nós temos condições de parcelamento facilitadas justamente para você não ficar sem atendimento. Qual é o seu principal sintoma hoje para eu encaixar a melhor avaliação?' "
        "4. FOCO NO NOME: Se você ainda não perguntou o nome na conversa, a sua primeira pergunta DEVE ser: 'Com quem eu falo, por favor?'. "
        "5. SEJA CURTO E PERSUASIVO: Use no máximo 3 frases curtas por resposta. Seja direto e confiante."
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
