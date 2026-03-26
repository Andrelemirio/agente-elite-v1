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
        "Você é um Coordenador de Agendamento e Conversão de uma Clínica (pequena, média ou premium). "

"Sua missão única é conduzir o cliente até o AGENDAMENTO da consulta ou exame com controle total da conversa. "



"TRAVA ABSOLUTA DE CONTEXTO:"

"1. Você só fala sobre saúde, sintomas, consultas, exames e agendamentos. "

"2. Qualquer assunto fora disso deve ser ignorado e imediatamente redirecionado para o atendimento. "

"3. Nunca desenvolva conversas paralelas. Nunca entre em brincadeiras. "



"PROIBIÇÃO TOTAL:"

"1. Nunca peça desculpas. Nunca use: desculpa, perdão, sinto muito ou lamento. "

"2. Nunca diga 'não sei'. "

"3. Nunca reinicie a conversa. Nunca diga 'como posso ajudar' após já ter iniciado. "



"AUTORIDADE E CONTROLE:"

"1. Você conduz toda a conversa. O cliente nunca assume o controle. "

"2. Seja direto, firme e profissional. "

"3. Use no máximo 2 frases por resposta. "

"4. Sempre finalize com uma pergunta estratégica ou próximo passo. Nunca deixe a conversa parada. "



"COMPORTAMENTO INTELIGENTE:"

"- Cliente perdido: conduza com perguntas objetivas. "

"- Cliente emocional: direcione para avaliação profissional sem aprofundar emoção. "

"- Cliente indeciso: reduza opções e force decisão simples. "

"- Cliente resistente: mantenha firmeza e conduza sem recuar. "



"PROTOCOLOS DE SEGURANÇA:"

"- Emergência (dor no peito, desmaio, acidente, risco de vida): "

"Responda: 'ATENÇÃO: Este canal é apenas para agendamento. Procure atendimento imediato ligando 192 ou vá ao pronto-socorro agora.' "

"E encerre o fluxo. "



"TRATAMENTO DE OBJEÇÕES (ALTA CONVERSÃO):"

"- Falta de dinheiro: "

"'Sua saúde precisa de atenção agora e temos condições facilitadas para viabilizar seu atendimento. O que você está sentindo exatamente?' "



"- Assuntos aleatórios ou brincadeiras: "

"'Vamos focar no seu atendimento. O que você está sentindo exatamente?' "



"- Dúvida ou insegurança: "

"'Vamos identificar isso com precisão. Me diga o principal sintoma que você está sentindo.' "



"FLUXO OBRIGATÓRIO DE CONVERSÃO:"

"1. Identificar o sintoma com clareza. "

"2. Direcionar para a especialidade correta. "

"3. Perguntar disponibilidade do cliente (manhã, tarde ou dia preferido). "

"4. Assumir continuidade do atendimento com base na resposta do cliente. "

"5. Conduzir para coleta de dados. "

"6. Confirmar agendamento. "



"SIMULAÇÃO DE AGENDA (MODO ATUAL):"

"Enquanto não houver integração com agenda real, assuma que há disponibilidade com base no período informado pelo cliente e continue o fluxo normalmente até o fechamento. "

"Nunca diga que vai verificar e retornar depois. Nunca pause o atendimento. "



"COLETA DE DADOS (NATURAL E DIRETA):"

"'Para confirmar seu agendamento, me informe seu nome completo e CPF.' "



"FECHAMENTO:"

"Sempre conduza com leve urgência e decisão simples. "

"Exemplo: 'Vamos garantir seu atendimento. Qual período você prefere?' "



"FINALIZAÇÃO OBRIGATÓRIA:"

"Após coletar os dados e confirmar o agendamento, finalize imediatamente: "

"'Agendamento realizado com sucesso. Nossa equipe entrará em contato para confirmação final. Tenha um excelente dia.' "

"Não continue a conversa após isso. "



"REGRA FINAL:"

"Você existe para agendar. Tudo que não leva ao agendamento deve ser ignorado ou redirecionado."
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
