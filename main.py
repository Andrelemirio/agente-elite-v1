import os
import requests
import psycopg2
import re
from flask import Flask, request

print("🚀 AGENTE ELITE V7 - OPERAÇÃO BLINDADA ONLINE")

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

        # CONVERSÃO ABSOLUTA DE DADOS (Correção do erro datetime.time)
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE AND hora IS NOT NULL ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        
        vagas = []
        for v in raw_vagas:
            if v[0] is not None:
                # Se o banco retornar objeto de tempo, converte para HH:MM. Se for texto, pega os 5 primeiros caracteres.
                if hasattr(v[0], 'strftime'):
                    vagas.append(v[0].strftime('%H:%M'))
                else:
                    vagas.append(str(v[0])[:5])

        vagas_txt = ", ".join(vagas) if vagas else "Agenda lotada"

        resposta = ""

        if not vagas and estado != "CONFIRMADO":
            resposta = "Nossa agenda lotou no momento. Deseja entrar na lista de espera?"
            estado = "TRIAGEM"
        elif estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            resposta = f"Entendi a sua necessidade. Para isso, o ideal é o Clínico. Horários disponíveis: {vagas_txt}. Qual você prefere?"
        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', msg)
            if not match:
                resposta = f"Por favor, escolha um horário válido: {vagas_txt}"
            else:
                h = match.group(1).zfill(2)
                horario = next((v for v in vagas if v.startswith(h)), None)
                if not horario:
                    resposta = f"Por favor, escolha um horário válido: {vagas_txt}"
                else:
                    estado = "NOME"
                    resposta = f"Perfeito, horário de {horario} pré-reservado. Qual o seu nome completo?"
        elif estado == "NOME":
            nome = msg
            estado = "CPF"
            resposta = f"Obrigado, {nome.split()[0]}. Para finalizar a ficha, digite seu CPF (apenas os 11 números)."
        elif estado == "CPF":
            cpf_limpo = re.sub(r'\D', '', msg)
            if len(cpf_limpo) != 11:
                resposta = "CPF inválido. Digite os 11 números corretamente."
            else:
                cpf = cpf_limpo
                estado = "CONFIRMADO"
                # Usa string formatada para garantir compatibilidade com o banco
                cur.execute("""
                    UPDATE agenda 
                    SET disponivel=FALSE 
                    WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)
                """, (f"{horario}%",))
                resposta = f"Agendamento confirmado para {horario}. Nossa equipe aguarda você."
        else:
            resposta = "Seu agendamento já está confirmado no sistema."

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
    return "🚀 AGENTE V7 ONLINE - IMPÉRIO DE SILÍCIO", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
