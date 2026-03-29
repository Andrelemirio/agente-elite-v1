import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE ELITE V7 - COORDENADOR DE ELITE ONLINE")

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
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"📤 ENVIO WHATS: {res.status_code}")
    except Exception as e:
        print(f"❌ ERRO ENVIO: {e}")

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    print("\n📩 NOVA REQUISIÇÃO RECEBIDA DA Z-API!")
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

        print(f"📞 TEL: {telefone} | 💬 MSG: {msg}")

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
            print("⚠️ MSG DUPLICADA IGNORADA")
            return "OK", 200

        # CONVERSÃO ABSOLUTA DE DADOS
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

        # LÓGICA DE COORDENADOR DE ELITE + MULTI-AGENDAMENTO
        if not vagas and estado not in ["CONFIRMADO", "CPF"]:
            resposta = "No momento, nossos especialistas estão com a agenda lotada para hoje. Como a sua saúde é prioridade, gostaria que eu te incluísse na nossa lista de espera VIP para o primeiro encaixe?"
            estado = "TRIAGEM"
            
        elif estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            resposta = f"Compreendo perfeitamente o que está sentindo. O profissional mais indicado para te avaliar com excelência é o nosso Clínico. Separei estes horários exclusivos para você: {vagas_txt}. Qual fica melhor na sua rotina?"
            
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            if not match:
                resposta = f"Para garantirmos a sua vaga com rapidez, por favor, me confirme um destes horários disponíveis: {vagas_txt}."
            else:
                h = match.group(1).zfill(2)
                horario = next((v for v in vagas if v.startswith(h)), None)
                if not horario:
                    resposta = f"Este horário acabou de ser preenchido. Ainda temos estas opções para te atender: {vagas_txt}. Qual prefere?"
                else:
                    estado = "NOME"
                    resposta = f"Excelente escolha. Seu horário das {horario} está pré-reservado. Para abrirmos a sua ficha de atendimento, qual é o nome completo do paciente?"
                    
        elif estado == "NOME":
            nome = msg
            estado = "CPF"
            resposta = f"Muito prazer, {nome.split()[0]}. Para a segurança dos seus dados e emissão do prontuário, digite apenas os 11 números do seu CPF, por favor."
            
        elif estado == "CPF":
            cpf_limpo = re.sub(r'\D', '', msg)
            if len(cpf_limpo) != 11:
                resposta = "Identifiquei que faltam alguns números. Por favor, digite os 11 dígitos do CPF para concluirmos."
            else:
                cpf = cpf_limpo
                estado = "CONFIRMADO"
                cur.execute("""
                    UPDATE agenda 
                    SET disponivel=FALSE 
                    WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)
                """, (f"{horario}%",))
                resposta = f"Tudo certo! Seu agendamento para {horario} está 100% confirmado. Nossa equipe de especialistas está pronta para te receber e garantir a melhor experiência possível. Até logo!"
                
        elif estado == "CONFIRMADO":
            if any(palavra in msg.lower() for palavra in ["obrigad", "ok", "valeu", "tchau", "certo", "beleza", "show", "agradeço"]):
                resposta = "Foi um prazer atender você. Nossa clínica está sempre à disposição. Um excelente dia!"
            else:
                if not vagas:
                    resposta = "Notei que você deseja realizar mais um agendamento, mas nossas vagas acabaram de encerrar. Deseja entrar na lista de espera para o próximo horário disponível?"
                    estado = "TRIAGEM"
                else:
                    nome = None
                    cpf = None
                    horario = None
                    sintoma = msg
                    estado = "AGENDAMENTO"
                    resposta = f"Com certeza, será um prazer cuidar de mais alguém da sua família. Os horários que ainda temos disponíveis são: {vagas_txt}. Qual você escolhe?"

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
    return "🚀 AGENTE V7 ONLINE - COORDENADOR DE ELITE", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
