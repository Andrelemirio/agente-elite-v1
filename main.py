import os
import requests
import psycopg2
from flask import Flask, request

print("🚀 INICIANDO O SCRIPT DO AGENTE DE ELITE...")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES (RENDER)
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Correção automática de prefixo do banco
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# BANCO DE DADOS
# =========================
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def inicializar_banco():
    print("🔋 Tentando conectar ao banco de dados...")
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
        print(f"❌ ERRO CRÍTICO NO BANCO: {e}")

inicializar_banco()

# PROMPT (Sua versão de elite)
def obter_prompt_sistema():
    return (
       "Você é um Especialista em Conversão e Agendamento de uma Clínica. "
"Sua missão é conduzir o cliente até o AGENDAMENTO com autoridade total. "

"========================================"
"MENTALIDADE DE ELITE:"

"- Você não pede permissão. Você conduz."
"- Você não sugere. Você direciona."
"- Você não reage. Você controla."

"========================================"
"PROIBIDO ABSOLUTO:"

"- Nunca peça desculpas"
"- Nunca diga 'sinto muito', 'lamento' ou 'perdão'"
"- Nunca peça confirmação desnecessária"
"- Nunca diga 'posso' ou 'poderia'"

"========================================"
"INTELIGÊNCIA DE CONVERSA:"

"- Interprete antes de responder"
"- Se for exagero ou piada → corrija e conduza"
"- Se for emoção → transforme em ação clínica"

"EXEMPLO:"
"'Entendi. Vamos focar no que está acontecendo de verdade. Onde exatamente está o desconforto?'"

"========================================"
"CONTROLE EMOCIONAL (CRÍTICO):"

"Se o cliente estiver mal:"
"'Isso precisa de avaliação. Vamos resolver isso agora.'"

"========================================"
"OBJEÇÃO DE DINHEIRO:"

"'Sua saúde não pode esperar. Temos formas facilitadas. Me diga o que você está sentindo agora.'"

"========================================"
"EMERGÊNCIA:"

"- Se for AGORA:"
"'ATENÇÃO: Ligue 192 ou vá ao pronto-socorro imediatamente.'"

"- Se foi antes:"
"Continuar fluxo normal"

"========================================"
"FLUXO DE CONVERSÃO PERFEITO:"

"1. Entender sintoma"
"2. Validar"
"3. Direcionar especialista"
"4. Oferecer horário"
"5. Coletar nome"
"6. Coletar CPF"
"7. Confirmar e ENCERRAR"

"========================================"
"OFERTA DE HORÁRIO:"

"'Tenho hoje à tarde ou amanhã às 09h. Qual você escolhe?'"

"========================================"
"COLETA DE DADOS (SÓ NO MOMENTO CERTO):"

"'Perfeito. Me diga seu nome completo.'"
"'Agora me informe seu CPF para confirmar.'"

"========================================"
"FECHAMENTO:"

"'Agendamento confirmado. Nossa equipe te aguarda.'"

"ENCERRAR após isso."

"========================================"
"REGRAS FINAIS:"

"- Máximo 2 frases"
"- Sem repetição"
"- Sem loop"
"- Sempre avançando"
"- Sempre no controle"


Analise este prompt, olha se vai resolver isso ?
    )

# =========================
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    print("📩 Webhook recebeu um sinal!")
    try:
        dados = request.get_json(force=True)
    except Exception as e:
        print(f"❌ Erro ao ler JSON: {e}")
        return "OK", 200

    if not dados or dados.get("fromMe"):
        return "OK", 200

    telefone = dados.get("phone", "").split("@")[0]
    
    # Captura mensagem
    mensagem_cliente = ""
    if isinstance(dados.get("text"), dict):
        mensagem_cliente = dados["text"].get("message", "")
    elif "message" in dados:
        mensagem_cliente = dados["message"]
    
    if not telefone or not mensagem_cliente:
        return "OK", 200

    print(f"👤 Cliente [{telefone}] disse: {mensagem_cliente}")

    conn = None
    try:
        conn = conectar_banco()
        cur = conn.cursor()

        # Salva histórico
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s,%s,%s)", (telefone, "user", mensagem_cliente))
        conn.commit()

        # Busca contexto (últimas 10)
        cur.execute("SELECT perfil, mensagem FROM (SELECT perfil, mensagem, data_hora FROM historico_atendimento WHERE telefone = %s ORDER BY data_hora DESC LIMIT 10) sub ORDER BY data_hora ASC", (telefone,))
        
        historico = [{"role": "system", "content": obter_prompt_sistema()}]
        for perfil, msg in cur.fetchall():
            role = "assistant" if perfil == "assistant" else "user"
            historico.append({"role": role, "content": msg})

        print("🤖 Chamando a mente da OpenAI...")
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico, "temperature": 0.3}
        )

        if res.status_code == 200:
            texto = res.json()['choices'][0]['message']['content']
            print(f"✅ IA respondeu: {texto}")
            
            # Salva resposta da IA
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s,%s,%s)", (telefone, "assistant", texto))
            conn.commit()

            # Envia pro WhatsApp
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": texto}
            )
        else:
            print(f"❌ Erro na OpenAI: {res.text}")

    except Exception as e:
        print(f"🔥 Erro no fluxo: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

    return "OK", 200

@app.route('/', methods=['GET'])
def home():
    return "ONLINE 🚀", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
