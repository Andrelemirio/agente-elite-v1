import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V10 - OVERRIDE GLOBAL E ANTI-LOOP ATIVO")

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

# =========================
# BANCO
# =========================
def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
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
    conn.close()

init_db()

# =========================
# WHATSAPP
# =========================
def enviar_whatsapp(telefone, mensagem):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    try:
        requests.post(
            url,
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
            json={"phone": telefone, "message": mensagem},
            timeout=10
        )
    except Exception as e:
        print(f"Erro ao enviar WhatsApp: {e}")

# =========================
# WEBHOOK
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)

        if not data or data.get("fromMe"):
            return "OK", 200

        telefone = data.get("phone", "")
        if "@" in telefone:
            telefone = telefone.split("@")[0]
            
        msg = ""
        if "text" in data:
            if isinstance(data["text"], dict):
                msg = data["text"].get("message", "")
            else:
                msg = str(data["text"])
        elif "message" in data:
            msg = str(data["message"])

        if not telefone or not msg:
            return "OK", 200

        msg = msg.strip()
        msg_lower = msg.lower()

        conn = conectar()
        cur = conn.cursor()

        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        sessao = cur.fetchone()

        if not sessao:
            estado, nome, cpf, sintoma, horario, ultima_msg = "TRIAGEM", None, None, None, None, None
            cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, %s)", (telefone, estado))
            conn.commit()
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = sessao

        if msg == ultima_msg:
            return "OK", 200

        # =========================
        # 1. PAUSA HUMANA
        # =========================
        palavras_pausa = ["espera", "aguarda", "um momento", "já volto", "ja volto", "calma", "pera"]
        if any(p in msg_lower for p in palavras_pausa):
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg, telefone))
            conn.commit()
            enviar_whatsapp(telefone, "Perfeito, fico no aguardo. Me avise quando puder continuarmos.")
            return "OK", 200

        # =========================
        # 2. OVERRIDE GLOBAL (QUEBRA DE PADRÃO E RESTART)
        # =========================
        palavras_reinicio = ["início", "inicio", "recomeçar", "voltar", "outra consulta", "nova consulta", "marcar outra", "marcar consulta", "mais uma", "novo agendamento", "outra marcação"]
        if any(p in msg_lower for p in palavras_reinicio) and estado != "TRIAGEM":
            estado = "TRIAGEM"
            nome = None
            cpf = None
            horario = None
            sintoma = None
            
            cur.execute("""
            UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s
            WHERE telefone=%s
            """, (estado, nome, cpf, sintoma, horario, msg, telefone))
            conn.commit()
            
            enviar_whatsapp(telefone, "Compreendido. Vamos iniciar um novo agendamento. Para qual especialidade médica ou sintoma você busca atendimento agora?")
            return "OK", 200

        # =========================
        # BUSCA AGENDA
        # =========================
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        
        vagas_lista = []
        for v in raw_vagas:
            if v[0] is not None:
                if hasattr(v[0], 'strftime'):
                    vagas_lista.append(v[0].strftime('%H:%M'))
                else:
                    vagas_lista.append(str(v[0])[:5])

        vagas_txt = ", ".join(vagas_lista) if vagas_lista else ""
        resposta = ""

        # =========================
        # FLUXO CONTROLADO
        # =========================

        if not vagas_lista and estado not in ["LISTA_ESPERA_CONFIRMACAO", "LISTA_ESPERA_DADOS", "CONFIRMADO", "FINALIZADO"]:
            estado = "LISTA_ESPERA_CONFIRMACAO"
            resposta = "Nossa agenda de hoje acabou de lotar. Deseja entrar na nossa lista de espera prioritária?"
            
        # TRIAGEM
        elif estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            resposta = f"Entendido. Para esse caso o ideal é passarmos por avaliação. Tenho os seguintes horários livres: {vagas_txt}. Qual horário você prefere?"

        # AGENDAMENTO
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            if not match:
                # Anti-loop dinâmico: Se o cliente responder com texto, o bot adapta e recua.
                estado = "TRIAGEM"
                sintoma = None
                resposta = "Entendi, vamos reajustar. Por favor, me confirme a especialidade ou o sintoma para eu buscar a melhor opção de horário."
            else:
                h_dig = match.group(1).zfill(2)
                h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)

                if not h_final:
                    resposta = f"Este horário não está disponível. Por favor, escolha uma destas opções válidas: {vagas_txt}"
                else:
                    horario = h_final
                    estado = "DADOS_NOME"
                    resposta = f"Excelente. O horário das {horario} está pré-reservado. Qual é o nome completo do paciente?"

        # NOME
        elif estado == "DADOS_NOME":
            nome = msg
            estado = "DADOS_CPF"
            primeiro_nome = nome.split()[0]
            resposta = f"Muito prazer, {primeiro_nome}. Para finalizar a ficha, digite o CPF do paciente (apenas os 11 números)."

        # CPF
        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', msg)

            if len(cpf_limpo) != 11 or cpf_limpo == cpf_limpo[0] * 11:
                resposta = "O CPF parece inválido. Por favor, digite os 11 números corretamente."
            else:
                cpf = cpf_limpo
                estado = "CONFIRMADO"

                cur.execute("""
                UPDATE agenda SET disponivel=FALSE
                WHERE id IN (
                    SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1
                )
                """, (f"{horario}%",))

                resposta = f"Tudo certo! Agendamento confirmado para as {horario}. Nossa equipe espera por você."

        # LISTA ESPERA CONFIRMAÇÃO
        elif estado == "LISTA_ESPERA_CONFIRMACAO":
            if any(p in msg_lower for p in ["sim", "quero", "pode", "ok", "claro"]):
                estado = "LISTA_ESPERA_DADOS"
                resposta = "Excelente. Por favor, me informe o nome completo do paciente para a lista de espera."
            else:
                estado = "TRIAGEM"
                resposta = "Compreendo. Agradecemos o contato e estamos à disposição para agendamentos futuros."

        # LISTA ESPERA DADOS
        elif estado == "LISTA_ESPERA_DADOS":
            nome = msg
            estado = "FINALIZADO"
            primeiro_nome = nome.split()[0]
            resposta = f"Perfeito, {primeiro_nome}. Você foi incluído(a) na lista de espera. Avisaremos assim que surgir uma vaga."

        # FINAL
        else:
            palavras_encerramento = ["obrigad", "ok", "valeu", "tchau", "certo", "beleza", "show"]
            if any(p in msg_lower for p in palavras_encerramento) and len(msg.split()) <= 4:
                resposta = "Eu que agradeço! A clínica está à disposição. Tenha um excelente dia!"
            else:
                estado = "CONFIRMADO"
                resposta = "Seu agendamento já está confirmado. Se precisar marcar uma nova consulta, é só me avisar!"

        # =========================
        # SALVAR ESTADO
        # =========================
        cur.execute("""
        UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s
        WHERE telefone=%s
        """, (estado, nome, cpf, sintoma, horario, msg, telefone))

        conn.commit()

        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print(f"❌ ERRO GERAL NO WEBHOOK: {e}")

    finally:
        if conn:
            conn.close()

    return "OK", 200

# =========================
# RESET
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()

        cur.execute("DELETE FROM agenda;")
        cur.execute("DELETE FROM sessoes;")

        for h in ["09:00", "11:00", "14:30", "16:00"]:
            cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))

        conn.commit()
        return "✅ RESET OK", 200
    except Exception as e:
        return f"❌ ERRO NO RESET: {e}", 500
    finally:
        if conn:
            conn.close()

# =========================
# START
# =========================
@app.route('/')
def home():
    return "🚀 IMPÉRIO DE SILÍCIO V10 ONLINE", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
