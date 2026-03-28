import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE V5.0 IMPERADOR - FULL POWER")

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURAÇÕES DE AMBIENTE
# ==========================================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Correção para o Heroku/Render (Postgres exige postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ==========================================
# 🗄️ GESTÃO DE BANCO DE DADOS
# ==========================================
def conectar_banco():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def inicializar_banco():
    """Garante que a estrutura de tabelas exista no banco de dados"""
    conn = conectar_banco()
    cur = conn.cursor()
    # Tabela de Histórico (Para memória de curto prazo)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historico_atendimento (
            id SERIAL PRIMARY KEY, 
            telefone VARCHAR(50), 
            perfil VARCHAR(20), 
            mensagem TEXT
        )
    """)
    # Tabela de Agenda (Para marcação real)
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

# Inicia as tabelas assim que o código sobe
inicializar_banco()

# ==========================================
# 🧠 O CÉREBRO (PROMPT DE AUTORIDADE)
# ==========================================
def obter_prompt_sistema(vagas):
    return f"""
Você é o Coordenador-Geral de Atendimento da Clínica. Você tem 20 anos de experiência e não aceita ser enrolado. Você é a AUTORIDADE máxima aqui.

PERSONALIDADE:
- Perspicaz: Identifica piadas, ironias e urgências reais imediatamente.
- Líder: Você conduz a conversa. Se o paciente se perder, você o traz de volta com firmeza e educação.
- Sem Robotização: Varie seu vocabulário. Nunca use as mesmas frases "prontas".
- Humano: Demonstre que se importa com a família do paciente, mas mantenha o foco no agendamento.

REGRAS DE OURO:
1. MÚLTIPLOS PEDIDOS: Se o paciente quer marcar para várias pessoas, aceite o desafio: "Entendi, André. Vamos organizar a agenda da família agora. Me conte quem é o primeiro e qual o sintoma, para eu definir os especialistas."
2. MALÍCIA: Se o paciente falar algo absurdo (como o acidente do tio), foque na gravidade real do acidente, não na piada. 
3. NÃO DIAGNOSTIQUE: Deixe claro que só o médico avalia, e use isso como gancho para fechar o horário.
4. PRIORIDADE: Dor no peito ou falta de ar? Pare tudo e mande para o 192/Emergência.

VAGAS REAIS PARA HOJE/AMANHÃ:
{vagas if vagas else "Consulte a recepção para possíveis encaixes de emergência."}

CONFIRMAÇÃO FINAL:
Só confirme após receber Nome e CPF. Diga algo natural como: 
"Tudo certo, [NOME]! O horário das [HORA] está oficialmente bloqueado para você. Estaremos prontos para te receber."
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

        # 1. BLOQUEIO DE DUPLICIDADE (Z-API Delay)
        cur.execute("SELECT mensagem FROM historico_atendimento WHERE telefone=%s ORDER BY id DESC LIMIT 1", (telefone,))
        ultima = cur.fetchone()
        if ultima and ultima[0] == msg: return "OK", 200

        # 2. SALVAR MENSAGEM DO USUÁRIO
        cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "user", msg))
        conn.commit()

        # 3. BUSCAR VAGAS REAIS NO BANCO
        cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 5")
        vagas_db = cur.fetchall()
        vagas_formatadas = ", ".join([v[0].strftime('%H:%M') for v in vagas_db])

        # 4. MEMÓRIA DE ELEFANTE (Últimas 15 mensagens para contexto total)
        cur.execute("""
            SELECT perfil, mensagem FROM (
                SELECT id, perfil, mensagem FROM historico_atendimento 
                WHERE telefone = %s ORDER BY id DESC LIMIT 15
            ) sub ORDER BY id ASC
        """, (telefone,))
        
        historico_ia = [{"role": "system", "content": obter_prompt_sistema(vagas_formatadas)}]
        for perfil, mensagem in cur.fetchall():
            historico_ia.append({"role": "assistant" if perfil == "assistant" else "user", "content": mensagem})

        # 5. CHAMADA OPENAI (Temperatura 0.6 para mais "malícia" e variação)
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "gpt-3.5-turbo", "messages": historico_ia, "temperature": 0.6}
        )

        if res.status_code == 200:
            resposta = res.json()['choices'][0]['message']['content']
            
            # 6. SALVAR RESPOSTA DA IA
            cur.execute("INSERT INTO historico_atendimento (telefone, perfil, mensagem) VALUES (%s, %s, %s)", (telefone, "assistant", resposta))
            conn.commit()
            
            # 7. ENVIAR VIA Z-API
            requests.post(
                f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                json={"phone": telefone, "message": resposta}
            )

            # 8. BAIXA INTELIGENTE NA AGENDA
            if "agendamento" in resposta.lower() and ("bloqueado" in resposta.lower() or "garantido" in resposta.lower() or "sucesso" in resposta.lower()):
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
# 🛠️ UTILITÁRIOS (RESET E HOME)
# ==========================================
@app.route('/reset-agenda', methods=['GET'])
def reset():
    """Limpa e repopula a agenda para novos testes"""
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
        return "✅ AGENDA IMPERADOR RESETADA E PRONTA!", 200
    except Exception as e:
        return f"Erro ao resetar: {e}", 500

@app.route('/', methods=['GET'])
def home():
    return "🚀 IMPÉRIO DE SILÍCIO V5.0 - STATUS: ONLINE E DOMINANDO", 200

if __name__ == '__main__':
    # Porta padrão para Render/Heroku ou 10000 local
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
