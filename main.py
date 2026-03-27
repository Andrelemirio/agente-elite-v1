import os
import requests
import psycopg2
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE DE ELITE INICIANDO...")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DE AMBIENTE
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Ajuste automático para o link do banco no Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# GESTÃO DO BANCO DE DADOS
# =========================
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

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
        print("🏛️ BANCO DE DADOS: CONECTADO E PRONTO!")
    except Exception as e:
        print(f"❌ ERRO NO BANCO: {e}")

inicializar_banco()

# =========================
# O PROMPT DE ELITE (CELEBRO)
# =========================
def obter_prompt_sistema():
    return (
        "Você é o Coordenador Sênior da Clínica. Sua missão é AGENDAR com autoridade total. "
        "MENTALIDADE DE ELITE: Você não pede permissão, você conduz. Não sugere, você direciona. "
        "PROIBIDO: Nunca peça desculpas. Nunca diga 'sinto muito', 'lamento', 'posso' ou 'poderia'. "
        
        "INTELIGÊNCIA DE CONVERSA: "
        "- Se o cliente exagerar ou fizer piada (ex: dor no fio de cabelo), questione o realismo antes de sugerir médico. "
        "- Filtre antes de agir: 'Entendi. Para sermos precisos, onde dói de verdade?' "
        
        "FLUXO OBRIGATÓRIO (NÃO PULE ETAPAS): "
        "1. Sintoma -> 2. Validar -> 3. Sugerir Especialista -> 4. Oferecer Horário -> 5. Nome -> 6. CPF. "
        
        "REGRAS DE OURO: "
        "- Máximo 2 frases por resposta. "
        "- Nunca peça CPF antes do Nome e do Horário definido. "
        "- Se citar DINHEIRO: 'Sua saúde não espera. Temos facilidades. O que você sente agora?' (Não peça dados aqui). "
        "- EMERGÊNCIA AGORA: 'Ligue 192 ou vá ao pronto-socorro imediatamente.' (Pare de responder). "
        
        "OFERTA DE HORÁRIO: 'Tenho hoje à tarde ou amanhã às 09h. Qual você escolhe?' "
        "FECHAMENTO: 'Agendamento confirmado. Nossa equipe te aguarda.' (Finalize)."
    )

# =========================
# WEBHOOK (O MOTOR)
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
    mensagem_cliente = ""

    if isinstance(dados.get("text"), dict):
        mensagem_cliente = dados["text"].get("message", "")
    elif "message" in dados:
        mensagem_cliente = dados["message"]

    if not telefone or not mensagem_cliente:
        return "OK", 200

    print(f"👤 [{telefone}]: {mensagem_cliente}")

    conn = None
    try:
        conn = conectar_banco()
        cur = conn.cursor()

        # Salva msg do cliente
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s,%s,%s)", (telefone, "user", mensagem_cliente))
        conn.commit()

        # Recupera histórico para contexto (últimas 10 mensagens)
        cur.execute("SELECT perfil, mensagem FROM (SELECT perfil, mensagem, data_hora FROM historico_atendimento WHERE telefone = %s ORDER BY data_hora DESC LIMIT 10) sub ORDER BY data_hora ASC", (telefone,))
        
        historico_ia = [{"role": "system", "content": obter_prompt_sistema()}]
        for perfil, msg in cur.fetchall():
            role = "assistant" if perfil == "assistant" else "user"
            historico_ia.append({"role": role, "content": msg})

        # Chamada OpenAI com TEMPERATURA 0.2 (Frieza e Precisão)
        res_openai = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": "gpt-3.5-turbo", 
                "messages": historico_ia, 
                "temperature": 0.2  # <--- AQUI ESTÁ O AJUSTE QUE VOCÊ PEDIU
            }
        )

        if res_openai.status_code == 200:
            resposta_texto = res_openai.json()['choices'][0]['message']['content']
            
            # Salva resposta do Robô
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s,%s,%s)", (telefone, "assistant", resposta_texto))
            conn.commit()
            print(f"🤖 IA: {resposta_texto}")

            # Envia via Z-API
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta_texto}
            )
        else:
            print(f"❌ Erro OpenAI: {res_openai.text}")

    except Exception as e:
        print(f"🔥 Erro no fluxo: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

    return "OK", 200

@app.route('/', methods=['GET'])
def home():
    return "AGENTE DE ELITE ONLINE 🚀", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
