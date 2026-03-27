import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO: AGENTE DE ELITE V2.5 - PREMIUM ATIVADO!")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DE AMBIENTE
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

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
        # 1. Controle de Estados (Cérebro do Atendimento)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS sessoes_atendimento (
                telefone VARCHAR(50) PRIMARY KEY,
                estado VARCHAR(50) DEFAULT 'TRIAGEM',
                horario_escolhido TIME,
                data_hora_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 2. Agenda Real (Estoque da Clínica)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS agenda_clinica (
                id SERIAL PRIMARY KEY,
                data DATE DEFAULT CURRENT_DATE + INTERVAL '1 day',
                hora TIME,
                disponivel BOOLEAN DEFAULT TRUE,
                paciente_nome TEXT,
                paciente_cpf TEXT,
                telefone_paciente VARCHAR(50)
            )
        ''')
        # 3. Histórico de Mensagens
        cur.execute('''
            CREATE TABLE IF NOT EXISTS historico_atendimento (
                id SERIAL PRIMARY KEY,
                telefone VARCHAR(50),
                perfil VARCHAR(20),
                mensagem TEXT
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("🏛️ INFRAESTRUTURA DE BANCO DE DADOS: OPERACIONAL!")
    except Exception as e:
        print(f"❌ ERRO NO BANCO: {e}")

inicializar_banco()

# =========================
# PROMPT DE ELITE BLINDADO
# =========================
def obter_prompt_sistema(estado, vagas):
    base_autoridade = (
        "Você é o Coordenador Sênior de Agendamento. Sua voz é de autoridade máxima, seca e profissional. "
        "DIRETRIZ: Você conduz a conversa. Não peça permissão, não use 'por favor' e nunca peça desculpas. "
        "Foco total em FECHAMENTO e TRIAGEM. Ignorar assuntos fora de saúde ou agendamento."
    )

    fases = {
        'TRIAGEM': (
            "ESTADO ATUAL: TRIAGEM. Objetivo: Identificar sintoma real. "
            "Se o sintoma for vago, confronte: 'Preciso do seu sintoma físico exato para prosseguir.' "
            "Não fale de horários nem de especialistas ainda. Só avance se o sintoma for validado."
        ),
        'AGENDAMENTO': (
            f"ESTADO ATUAL: ESCOLHA DE HORÁRIO. Horários reais disponíveis: {vagas if vagas else 'AGENDA LOTADA'}. "
            "Sugira o especialista correto para o sintoma. Exija que o cliente escolha um horário da lista."
        ),
        'DADOS': (
            "ESTADO ATUAL: COLETA DE DADOS. Peça o Nome Completo e depois o CPF para finalizar a reserva. "
            "Não aceite distrações. Somente após receber os dados, confirme o agendamento."
        )
    }

    return (
        f"{base_autoridade}\n\n"
        f"INSTRUÇÃO DE ESTADO: {fases.get(estado)}\n\n"
        "REGRAS CRÍTICAS:\n"
        "- Máximo 2 frases por resposta.\n"
        "- Se o cliente fugir do assunto, corte com: 'Meu foco é seu agendamento. Vamos retomar: [PERGUNTA].'\n"
        "- Finalização: Somente quando confirmar CPF, diga exatamente: 'Agendamento pré-confirmado. Equipe validará em instantes.'"
    )

# =========================
# MOTOR DE ESTADOS E RESERVAS
# =========================
def processar_fluxo(telefone, msg_cliente):
    conn = conectar_banco()
    cur = conn.cursor()
    
    cur.execute("SELECT estado FROM sessoes_atendimento WHERE telefone = %s", (telefone,))
    result = cur.fetchone()
    estado = result[0] if result else 'TRIAGEM'

    if not result:
        cur.execute("INSERT INTO sessoes_atendimento (telefone, estado) VALUES (%s, 'TRIAGEM')", (telefone,))
    
    # Detecção Inteligente de Mudança de Estado
    if estado == 'TRIAGEM' and len(msg_cliente) > 5: # Presume-se que descreveu sintoma
        estado = 'AGENDAMENTO'
    elif estado == 'AGENDAMENTO' and re.search(r'(\d{2}[:h]\d{2})', msg_cliente):
        estado = 'DADOS'
    
    cur.execute("UPDATE sessoes_atendimento SET estado = %s WHERE telefone = %s", (estado, telefone))
    conn.commit()
    cur.close()
    conn.close()
    return estado

def dar_baixa_no_banco(telefone, texto_resposta):
    if "Agendamento pré-confirmado" in texto_resposta:
        try:
            conn = conectar_banco()
            cur = conn.cursor()
            # Marca o primeiro horário livre (Simulando a escolha do cliente para o teste)
            cur.execute("UPDATE agenda_clinica SET disponivel = FALSE, telefone_paciente = %s WHERE disponivel = TRUE AND id = (SELECT id FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 1)", (telefone,))
            cur.execute("DELETE FROM sessoes_atendimento WHERE telefone = %s", (telefone,))
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ AGENDA ATUALIZADA: Vaga ocupada por {telefone}")
        except Exception as e:
            print(f"❌ Erro na baixa: {e}")

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json(force=True)
    if not dados or dados.get("fromMe"): return "OK", 200
    telefone = dados.get("phone", "").split("@")[0]
    msg = dados.get("text", {}).get("message", "") if isinstance(dados.get("text"), dict) else dados.get("message", "")
    if not msg: return "OK", 200

    # 1. Processa Inteligência de Estado
    estado_atual = processar_fluxo(telefone, msg)
    
    # 2. Busca Vagas Reais
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("SELECT hora FROM agenda_clinica WHERE disponivel = TRUE ORDER BY hora ASC LIMIT 4")
    vagas = ", ".join([v[0].strftime('%H:%M') for v in cur.fetchall()])

    # 3. OpenAI com Prompt Dinâmico
    res = requests.post("https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
                        json={
                            "model": "gpt-3.5-turbo", 
                            "messages": [{"role": "system", "content": obter_prompt_sistema(estado_atual, vagas)}, {"role": "user", "content": msg}], 
                            "temperature": 0.2
                        })

    if res.status_code == 200:
        resposta = res.json()['choices'][0]['message']['content']
        
        # 4. Envia Resposta e dá Baixa se necessário
        requests.post(f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text",
                      headers={"Client-Token": ZAPI_CLIENT_TOKEN},
                      json={"phone": telefone, "message": resposta})
        
        dar_baixa_no_banco(telefone, resposta)

    cur.close()
    conn.close()
    return "OK", 200

# =========================
# ROTAS DE ADMINISTRAÇÃO
# =========================
@app.route('/reset-agenda', methods=['GET'])
def reset():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("DELETE FROM agenda_clinica; DELETE FROM sessoes_atendimento;")
    for h in ['08:00', '09:30', '11:00', '14:30', '16:00']:
        cur.execute("INSERT INTO agenda_clinica (hora) VALUES (%s)", (h,))
    conn.commit()
    cur.close()
    conn.close()
    return "✅ AGENDA E SESSÕES RESETADAS!", 200

@app.route('/painel', methods=['GET'])
def painel():
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("SELECT hora, telefone_paciente FROM agenda_clinica WHERE disponivel = FALSE")
    agendados = cur.fetchall()
    html = "<h1>Agendamentos de Hoje</h1><ul>"
    for a in agendados:
        html += f"<li>Horário: {a[0]} | Telefone: {a[1]}</li>"
    html += "</ul>"
    cur.close()
    conn.close()
    return html, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
