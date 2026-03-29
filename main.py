import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE V9 - ATENDENTE SÊNIOR & INTELIGÊNCIA DE CONTEXTO")

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
# WEBHOOK PRINCIPAL (MOTOR DE FLUXO SÊNIOR)
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

        # REGRA CRÍTICA: CONTROLE DE CONVERSA (PAUSA)
        palavras_pausa = ["vou ver", "espera", "já te falo", "ja te falo", "vou perguntar", "um momento", "aguarda", "pera", "calma"]
        if any(p in msg.lower() for p in palavras_pausa):
            resposta_pausa = "Perfeito, fico no aguardo. Me avise quando tiver a informação para continuarmos o agendamento."
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

        vagas_txt = ", ".join(vagas) if vagas else ""

        resposta = ""

        # GESTÃO DE AGENDA LOTADA E LISTA DE ESPERA
        if not vagas and estado not in ["CONFIRMADO", "CPF", "NOME", "AGUARDANDO_ESPERA"]:
            resposta = "No momento nossa agenda para hoje está completamente preenchida. Posso te colocar na lista de espera prioritária?"
            estado = "AGUARDANDO_ESPERA"

        elif estado == "AGUARDANDO_ESPERA":
            if any(p in msg.lower() for p in ["sim", "pode", "quero", "ok", "por favor", "coloca", "pode ser"]):
                resposta = "Combinado. Adicionei o paciente na nossa lista de espera prioritária. Assim que surgir uma desistência ou novo horário, entro em contato imediatamente."
                estado = "CONFIRMADO"
            else:
                resposta = "Compreendo. Agradecemos o contato e estamos à disposição para agendamentos futuros."
                estado = "CONFIRMADO"
            
        elif estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            
            # Inteligência de Triagem
            msg_l = msg.lower()
            especialidade = "Clínico Geral" 
            if any(k in msg_l for k in ["peito", "coração", "coracao", "infarto", "pressão"]):
                especialidade = "Cardiologista"
            elif any(k in msg_l for k in ["estômago", "estomago", "diges", "barriga", "refluxo"]):
                especialidade = "Gastroenterologista"
            elif any(k in msg_l for k in ["muscul", "osso", "costa", "dor", "joelho", "coluna"]):
                especialidade = "Ortopedista"
                
            resposta = f"Entendido. Para esse caso, o especialista mais indicado é o {especialidade}. Nossos horários disponíveis são: {vagas_txt}. Qual desses horários fica melhor para o paciente?"
            
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            if not match:
                # Mudança de intenção ou sintoma
                estado = "TRIAGEM"
                sintoma = None
                resposta = "Entendi, vamos ajustar. Por favor, me confirme qual é a especialidade ou o motivo exato da consulta que você busca agora."
            else:
                h = match.group(1).zfill(2)
                # Interpretação parcial (ex: "16" mapeia para "16:00" ou "16:30")
                horario = next((v for v in vagas if v.startswith(h)), None)
                if not horario:
                    resposta = f"Este horário não consta na nossa disponibilidade atual. Por favor, escolha uma destas opções para garantirmos a vaga: {vagas_txt}."
                else:
                    estado = "NOME"
                    resposta = f"Ótimo. O horário das {horario} está reservado. Para iniciarmos o prontuário, qual é o nome completo do paciente que será atendido?"
                    
        elif estado == "NOME":
            nome = msg
            estado = "CPF"
            primeiro_nome = nome.split()[0]
            resposta = f"Muito prazer, {primeiro_nome}. Para finalizar o cadastro e validar a consulta, por favor, me informe o CPF do paciente (apenas os 11 números)."
            
        elif estado == "CPF":
            cpf_limpo = re.sub(r'\D', '', msg)
            msg_l = msg.lower()
            recusa_lgpd = ["não", "nao", "não quero", "precisa", "obrigatório", "lgpd", "motivo", "por que"]
            
            if len(cpf_limpo) == 11:
                cpf = cpf_limpo
                estado = "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Perfeito! Agendamento para as {horario} confirmado com sucesso. Nossa equipe aguarda o paciente. Até breve!"
            elif any(r in msg_l for r in recusa_lgpd) and len(msg.split()) < 15:
                cpf = "RECUSADO_LGPD"
                estado = "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Sem problemas. O pré-agendamento para as {horario} está garantido. Coletaremos os dados restantes presencialmente na recepção. Até logo!"
            else:
                resposta = "O CPF informado não parece válido. Digite exatamente os 11 números (ou, se preferir informar apenas presencialmente, me avise)."
                
        elif estado == "CONFIRMADO":
            msg_l = msg.lower()
            # Tratamento de Múltiplos Agendamentos
            if any(palavra in msg_l for palavra in ["outra pessoa", "mais um", "meu irmão", "minha", "meu", "marcar outro", "novo", "esposa", "marido"]):
                nome = None
                cpf = None
                horario = None
                sintoma = None
                estado = "TRIAGEM"
                resposta = "Claro, será um prazer ajudar com mais um agendamento. Por favor, me informe o motivo da consulta ou especialidade para este novo paciente."
            else:
                palavras_encerramento = ["obrigad", "ok", "valeu", "tchau", "certo", "beleza", "show", "agradeço"]
                if any(p in msg_l for p in palavras_encerramento) and len(msg.split()) <= 4:
                    resposta = "Eu que agradeço. A clínica está à sua disposição. Tenha um excelente dia!"
                else:
                    resposta = "Seu agendamento já está confirmado. Se precisar marcar para outra pessoa, é só me informar."

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
    return "🚀 AGENTE V9 ONLINE - IMPÉRIO DE SILÍCIO", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
