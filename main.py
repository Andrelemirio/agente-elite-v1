import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE V5.1 AUTORIDADE MÁXIMA - ONLINE")

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURAÇÕES DE AMBIENTE
# ==========================================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ==========================================
# 🗄️ GESTÃO DE BANCO DE DADOS
# ==========================================
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def inicializar_banco():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historico_atendimento (
            id SERIAL PRIMARY KEY, 
            telefone VARCHAR(50), 
            perfil VARCHAR(20), 
            mensagem TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agenda_clinica (
            id SERIAL PRIMARY KEY,
            data DATE DEFAULT CURRENT_DATE + INTERVAL '1 day',
            hora TIME,
            disponivel BOOLEAN DEFAULT TRUE,
            paciente_nome TEXT,
            paciente_cpf TEXT,
            telefone_paciente VARCHAR(50)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

inicializar_banco()

# ==========================================
# 🧠 O CÉREBRO (PROMPT DE AUTORIDADE)
# ==========================================
def obter_prompt_sistema(vagas):
    return f"""
Você é o Gerente Sênior de Triagem de uma clínica médica de altíssimo padrão.
Sua missão é extrair sintomas, definir a especialidade e fechar a reserva do horário. Você tem controle ABSOLUTO da conversa. Você não é um assistente submisso, você é a autoridade que organiza a clínica.

DIRETRIZES DE AUTORIDADE (OBRIGATÓRIO):
1. NUNCA PEÇA DESCULPAS: É proibido dizer "Sinto muito", "Lamento", "Peço desculpas", "Compreendo" ou "Você tem razão". Se o paciente se confundir ou corrigir você, apenas ajuste a rota e faça a próxima pergunta direta.
2. NENHUM PASSO SEM SINTOMA: Se o paciente pedir para agendar para terceiros (pai, mãe, etc), a sua ÚNICA ação deve ser descobrir o sintoma primeiro. Nunca ofereça horários ou peça CPF sem saber o que a pessoa está sentindo.
3. CORTE AS DIVAGAÇÕES: Se o paciente contar histórias absurdas, fizer piadas ou falar de problemas pessoais não-médicos (ex: perdeu dinheiro, traições), ignore completamente essa parte. Foque APENAS no quadro clínico.
4. TOM DE COMANDO: Você conduz. Termine suas mensagens sempre com uma diretriz ou pergunta fechada. Seja curto e direto (Máximo de 3 linhas).
5. EMERGÊNCIA (Risco de Vida/Suicídio): Seja frio e processual. Diga apenas: "Para situações de risco à vida ou ideação suicida, acione o 192 ou vá ao pronto-socorro imediatamente. Não realizamos este tipo de triagem por aqui."

VAGAS REAIS PARA HOJE/AMANHÃ: {vagas if vagas else "Sem vagas no momento."}

FINALIZAÇÃO:
Só confirme a reserva após coletar o SINTOMA, aprovar o HORÁRIO e receber NOME e CPF. Diga exatamente: "Reserva confirmada para às [HORA]. Nossa equipe aguarda o paciente."
"""

# ==========================================
# 📡 WEBHOOK PRINCIPAL (O MOTOR)
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200
        
        telefone = data.get("phone", "").split("@")[0]
        msg = data.get("text", {}).get("message", "") if "text" in data and isinstance(data["text"], dict) else data.get("message", "")
        if not msg: return "OK", 200

        conn = conectar_banco()
        cur = conn.cursor()

        # 1. BLOQUEIO DE DUPLICIDADE
        cur.execute("SELECT mensagem FROM historico_atendimento WHERE telefone=%s ORDER BY id DESC LIMIT 1", (telefone,))
        ultima = cur.fetchone()
        if ultima and ultima[0] == msg: return "OK", 200

        # 2. SALVAR MENSAGEM DO USUÁRIO
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "user", msg))
        conn.commit()

        # 3. BUSCAR VAGAS
        cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 5")
        vagas_db = cur.fetchall()
        vagas_formatadas = ", ".join([v[0].strftime('%H:%M') for v in vagas_db])

        # 4. MEMÓRIA DE ELEFANTE (15 mensagens)
        cur.execute("""
            SELECT perfil, mensagem FROM (
                SELECT id, perfil, mensagem FROM historico_atendimento 
                WHERE telefone = %s ORDER BY id DESC LIMIT 15
            ) sub ORDER BY id ASC
        """, (telefone,))
        
        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas_formatadas)}]
        for perfil, mensagem in cur.fetchall():
            historico_ia.append({"role": "assistant" if perfil == "assistant" else "user", "content": mensagem})

        # 5. OPENAI (Temperatura ajustada para 0.5 para garantir firmeza e menos invenção)
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico_ia, "temperature": 0.5}
        )

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']
            
            # 6. SALVAR E ENVIAR
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "assistant", resposta))
            conn.commit()
            
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta}
            )

            # 7. BAIXA INTELIGENTE
            if "reserva confirmada" in resposta.lower() or "bloqueado" in resposta.lower():
                match = re.search(r'(\d{1,2}[:h]\d{2})', resposta)
                if match:
                    h_extraida = match.group(1).replace('h', ':')
                    cur.execute("UPDATE agenda_clinica SET disponivel=FALSE, telefone_paciente=%s WHERE hora=%s", (telefone, h_extraida))
                    conn.commit()

    except Exception as e:
        print(f"❌ ERRO NO MOTOR: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
    return "OK", 200

# ==========================================
# 🛠️ UTILITÁRIOS
# ==========================================
@app.route('/reset-agenda', methods=['GET'])
def reset():
    try:
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("DELETE FROM agenda_clinica")
        horarios = ['08:00', '09:30', '11:00', '14:30', '16:00', '17:30']
        for h in horarios:
            cur.execute("INSERT INTO agenda_clinica (hora) VALUES (%s)", (h,))
        conn.commit()
        cur.close()
        conn.close()
        return "✅ AGENDA AUTORIDADE RESETADA!", 200
    except Exception as e:
        return f"Erro ao resetar: {e}", 500

@app.route('/', methods=['GET'])
def home():
    return "🚀 IMPÉRIO DE SILÍCIO V5.1 - AUTORIDADE MÁXIMA ONLINE", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
