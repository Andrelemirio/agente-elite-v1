import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE V8 - RECEPCIONISTA SÊNIOR & TRIAGEM INTELIGENTE ONLINE")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# =========================
# BANCO DE DADOS
# =========================
def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

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
        print("✅ BANCO OK")
    except Exception as e:
        print(f"❌ ERRO BANCO: {e}")
    finally:
        if conn:
            conn.close()

init_db()

# =========================
# WHATSAPP
# =========================
def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        headers = {"Client-Token": ZAPI_CLIENT_TOKEN}
        payload = {"phone": telefone, "message": mensagem}
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ ERRO ENVIO: {e}")

# =========================
# WEBHOOK PRINCIPAL (MOTOR DE FLUXO)
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

        if msg == ultima_msg:
            return "OK", 200

        # REGRA CRÍTICA 1: CONTROLE DE CONVERSA (PAUSA)
        palavras_pausa = ["vou ver", "espera", "já te falo", "ja te falo", "vou perguntar", "um momento", "aguarda", "pera"]
        if any(p in msg.lower() for p in palavras_pausa):
            resposta_pausa = "Perfeito, fico no aguardo. Me avise quando tiver a informação para continuarmos."
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta_pausa)
            return "OK", 200

        # BUSCA DE VAGAS
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE AND hora IS NOT NULL ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        
        vagas = []
        for v in raw_vagas:
            if v[0] is not None:
                if hasattr(v[0], 'strftime'):
                    vagas.append(v[0].strftime('%H:%M'))
                else:
                    vagas.append(str(v[0])[:5])

        vagas_txt = ", ".join(vagas) if vagas else "Agenda lotada"

        resposta = ""

        # REGRA CRÍTICA 2: FLUXO OBRIGATÓRIO & TRIAGEM INTELIGENTE
        if not vagas and estado not in ["CONFIRMADO", "CPF", "NOME"]:
            resposta = "Nossa agenda de hoje acabou de lotar. Deseja que eu adicione o paciente na lista de espera prioritária?"
            estado = "TRIAGEM"
            
        elif estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            
            # Inteligência de Triagem
            msg_l = msg.lower()
            especialidade = "Clínico Geral" # Triagem padrão de segurança
            if any(k in msg_l for k in ["peito", "coração", "coracao", "infarto"]):
                especialidade = "Cardiologista"
            elif any(k in msg_l for k in ["estômago", "estomago", "diges", "barriga"]):
                especialidade = "Gastroenterologista"
            elif any(k in msg_l for k in ["muscul", "osso", "costa", "dor", "joelho"]):
                especialidade = "Ortopedista"
                
            resposta = f"Compreendo. Para esse quadro, o ideal é passarmos com o {especialidade}. Nossos horários livres para esse atendimento são: {vagas_txt}. Qual é o melhor horário para o paciente?"
            
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            if not match:
                # Anti-loop (se o cliente mudar de ideia ou não informar número)
                estado = "TRIAGEM"
                sintoma = None
                resposta = "Certo, vamos reajustar. Qual é a especialidade exata ou o sintoma que o paciente está apresentando agora?"
            else:
                h = match.group(1).zfill(2)
                horario = next((v for v in vagas if v.startswith(h)), None)
                if not horario:
                    resposta = f"Esse horário não está disponível na grade. Para garantirmos a vaga com rapidez, me confirme um destes: {vagas_txt}."
                else:
                    estado = "NOME"
                    resposta = f"Excelente. O horário das {horario} está pré-reservado. Para abrirmos a ficha, qual é o nome completo do paciente?"
                    
        elif estado == "NOME":
            nome = msg
            estado = "CPF"
            resposta = f"Muito prazer, {nome.split()[0]}. Para a segurança dos dados e emissão do prontuário, digite apenas os 11 números do CPF do paciente."
            
        elif estado == "CPF":
            # REGRA CRÍTICA 3: LEIS E SEGURANÇA (LGPD / RECUSA CPF)
            cpf_limpo = re.sub(r'\D', '', msg)
            msg_l = msg.lower()
            recusa_lgpd = ["não", "nao", "não quero", "precisa", "obrigatório", "lgpd", "motivo", "por que"]
            
            if len(cpf_limpo) == 11:
                cpf = cpf_limpo
                estado = "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Tudo certo! Agendamento para {horario} 100% confirmado. Nossa equipe de especialistas aguarda o paciente. Até logo!"
            elif any(r in msg_l for r in recusa_lgpd) and len(msg.split()) < 15:
                cpf = "RECUSADO_LGPD"
                estado = "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Sem problemas, podemos deixar o pré-agendamento feito para {horario} e finalizar seus dados no atendimento presencial. Nossa equipe aguarda você!"
            else:
                resposta = "O CPF deve conter exatamente 11 números. (Ou, se preferir não informar agora, basta me avisar)."
                
        elif estado == "CONFIRMADO":
            palavras_encerramento = ["obrigad", "ok", "valeu", "tchau", "certo", "beleza", "show", "agradeço"]
            if any(p in msg.lower() for p in palavras_encerramento) and len(msg.split()) <= 4:
                resposta = "Foi um prazer atender você. Nossa clínica está sempre à disposição. Um excelente dia!"
            else:
                nome = None
                cpf = None
                horario = None
                sintoma = None
                estado = "TRIAGEM"
                resposta = "Com certeza, posso iniciar um novo agendamento. Qual é a especialidade médica ou sintoma do novo paciente?"

        cur.execute("""
            UPDATE sessoes 
            SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s 
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
# ROTAS DE SUPORTE
# =========================
@app.route('/reset', methods=['GET'])
def reset():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
        for h in ["09:00", "11:00", "14:30", "16:00"]:
            cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "✅ RESET OK", 200
    except Exception as e:
        return f"❌ ERRO NO RESET: {e}", 500
    finally:
        if conn:
            conn.close()

@app.route('/')
def home():
    return "🚀 AGENTE V8 ONLINE - IMPÉRIO DE SILÍCIO", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
