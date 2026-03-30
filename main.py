# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V11 — AGENTE DE ELITE
# INTELIGÊNCIA DE ATENÇÃO E MULTI-RECONHECIMENTO
# ============================================

import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V11 - OPERACIONAL")

app = Flask(__name__)

# =========================
# CONFIG
# =========================
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

# =========================
# INIT DB
# =========================
def init_db():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                telefone TEXT PRIMARY KEY,
                estado TEXT,
                nome TEXT,
                cpf TEXT,
                sintoma TEXT,
                horario TEXT,
                ultima_msg TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                id SERIAL PRIMARY KEY,
                hora TEXT,
                disponivel BOOLEAN DEFAULT TRUE
            )
        """)
        conn.commit()
    except Exception as e:
        print("Erro DB:", e)
    finally:
        if conn: conn.close()

init_db()

# =========================
# WHATSAPP
# =========================
def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
    except Exception as e:
        print("Erro WhatsApp:", e)

# =========================
# INTELIGÊNCIA DE TRIAGEM
# =========================
def detectar_especialidade(s):
    s = s.lower()
    if any(k in s for k in ["peito", "coração", "coracao", "pressão", "palpitação"]): return "Cardiologista"
    if any(k in s for k in ["dente", "canal", "limpeza", "dentadura"]): return "Dentista"
    if any(k in s for k in ["estômago", "estomago", "barriga", "refluxo", "azia"]): return "Gastroenterologista"
    if any(k in s for k in ["osso", "dor", "joelho", "coluna", "costa"]): return "Ortopedista"
    return "Clínico Geral"

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200

        telefone = data.get("phone", "")
        if "@" in telefone: telefone = telefone.split("@")[0]

        msg = ""
        if "text" in data:
            msg = data["text"].get("message", "") if isinstance(data["text"], dict) else str(data["text"])
        elif "message" in data:
            msg = str(data["message"])

        if not telefone or not msg: return "OK", 200
        msg_clean = msg.strip()
        msg_lower = msg_clean.lower()

        conn = conectar()
        cur = conn.cursor()

        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        row = cur.fetchone()

        if not row:
            estado, nome, cpf, sintoma, horario, ultima_msg = "TRIAGEM", None, None, None, None, None
            cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, %s)", (telefone, estado))
            conn.commit()
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        # BUSCA DE VAGAS
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        vagas_lista = []
        for v in raw_vagas:
            if v[0]:
                vagas_lista.append(v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5])

        vagas_txt = ", ".join(vagas_lista) if vagas_lista else ""
        resposta = ""

        # 1. OVERRIDE DE REINÍCIO OU MÚLTIPLOS
        palavras_reinicio = ["começar", "início", "inicio", "recomeçar", "voltar", "marcar outra", "mais uma", "marcar consulta"]
        if any(p in msg_lower for p in palavras_reinicio) and estado == "CONFIRMADO":
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            resposta = "Com certeza, será um prazer ajudar com mais um agendamento. Para qual especialidade médica ou sintoma você busca atendimento agora?"

        # 2. PAUSA
        elif any(p in msg_lower for p in ["espera", "aguarda", "um momento", "vou ver", "ja volto"]):
            enviar_whatsapp(telefone, "Sem problemas, fico no aguardo. Me avise quando puder continuarmos.")
            return "OK", 200

        # 3. FLUXO POR ESTADOS
        elif estado == "TRIAGEM":
            sintoma = msg_clean
            esp = detectar_especialidade(sintoma)
            estado = "AGENDAMENTO"
            if not vagas_lista:
                estado = "LISTA_ESPERA"
                resposta = f"Entendido. Para esse caso o ideal é o {esp}, mas nossa agenda está cheia hoje. Deseja entrar na lista de espera prioritária?"
            else:
                resposta = f"Entendi perfeitamente. O especialista indicado é o {esp}. Nossos horários disponíveis são: {vagas_txt}. Qual desses horários fica melhor para você?"

        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg_clean)
            
            # INTELIGÊNCIA DE ATENÇÃO (Paciente fazendo perguntas/comentários)
            if not match:
                if any(p in msg_lower for p in ["consegue", "pode", "outra", "outras", "pessoa", "tambem", "também", "ajudar"]):
                    resposta = "Com certeza! Consigo marcar para quantas pessoas você precisar. Mas para garantir que os dados fiquem corretos no sistema, vamos finalizar este primeiro agendamento agora. Qual destes horários você prefere: " + vagas_txt + "?"
                else:
                    resposta = f"Para garantirmos a sua vaga agora, por favor, me confirme apenas o número do horário desejado: {vagas_txt}"
            else:
                h_dig = match.group(1).zfill(2)
                h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
                if not h_final:
                    resposta = f"Desculpe, esse horário não está disponível. Por favor, escolha uma dessas opções: {vagas_txt}"
                else:
                    horario, estado = h_final, "DADOS_NOME"
                    resposta = f"Excelente. O horário das {horario} está pré-reservado. Qual é o nome completo do paciente que será atendido?"

        elif estado == "DADOS_NOME":
            if len(msg_clean.split()) < 2:
                resposta = "Para o prontuário, preciso do nome completo (nome e sobrenome). Como devo registrar?"
            else:
                nome, estado = msg_clean, "DADOS_CPF"
                resposta = f"Muito prazer, {nome.split()[0]}. Para finalizar a ficha e validar a consulta, digite o CPF do paciente (apenas os 11 números)."

        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', msg_clean)
            if len(cpf_limpo) != 11:
                resposta = "O CPF informado está incompleto. Por favor, digite os 11 números corretamente para confirmarmos."
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Tudo pronto! Seu agendamento para as {horario} está confirmado. Nossa equipe aguarda você. Se precisar marcar para outra pessoa, é só me avisar!"

        elif estado == "LISTA_ESPERA":
            if any(p in msg_lower for p in ["sim", "quero", "pode", "ok"]):
                estado, resposta = "CONFIRMADO", "Perfeito. Já te incluí na lista de espera prioritária. Entraremos em contato assim que surgir uma vaga!"
            else:
                estado, resposta = "TRIAGEM", "Entendido. Caso mude de ideia ou precise de outra especialidade, estou à disposição."

        else:
            resposta = "Seu agendamento já está confirmado. Gostaria de marcar para mais alguém?"

        # SALVAR
        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print("Erro Webhook:", e)
    finally:
        if conn: conn.close()
    return "OK", 200

# =========================
# RESET / HOME
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = None
    try:
        conn = conectar(); cur = conn.cursor()
        cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
        for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "✅ RESET V11 OK", 200
    except Exception as e: return str(e), 500
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 IMPÉRIO DE SILÍCIO V11 ATIVO", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
