import os
import requests
import psycopg2
import re
from flask import Flask, request

# Início do sistema no log do Render
print("🚀 IMPÉRIO DE SILÍCIO: V6.2 EDIÇÃO DE OURO - ONLINE")

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURAÇÕES DE AMBIENTE
# ==========================================
# Estas variáveis devem estar configuradas no Painel do Render
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Correção automática para o padrão do SQLAlchemy/Postgres no Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ==========================================
# 🗄️ GESTÃO DE BANCO DE DADOS
# ==========================================
def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    """Inicializa e atualiza a estrutura do banco de dados"""
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        
        # Tabela de Sessões (Estados da conversa)
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
        
        # Tabela de Agenda (Vagas reais)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                id SERIAL PRIMARY KEY,
                hora TEXT,
                disponivel BOOLEAN DEFAULT TRUE
            )
        """)
        
        conn.commit()
        print("✅ BANCO DE DADOS SINCRONIZADO E PRONTO")
    except Exception as e:
        print(f"❌ ERRO AO INICIAR BANCO: {e}")
    finally:
        if conn: conn.close()

# Rodar inicialização ao ligar o código
init_db()

# ==========================================
# 🛠️ FERRAMENTAS AUXILIARES
# =========================
def enviar_whatsapp(telefone, mensagem):
    """Envia a mensagem via Z-API"""
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        headers = {"Client-Token": ZAPI_CLIENT_TOKEN}
        payload = {"phone": telefone, "message": mensagem}
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no envio WhatsApp: {e}")

def validar_cpf(cpf):
    """Checa se o CPF tem 11 números"""
    nums = re.sub(r'\D', '', cpf)
    return len(nums) == 11

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
        # Captura a mensagem de texto do WhatsApp
        msg = ""
        if "text" in data and isinstance(data["text"], dict):
            msg = data["text"].get("message", "")
        else:
            msg = data.get("message", "")
        
        if not telefone or not msg: return "OK", 200

        conn = conectar()
        cur = conn.cursor()

        # 1. BUSCA OU CRIA A SESSÃO DO PACIENTE
        cur.execute("SELECT estado, nome, cpf, sintoma, horario, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        sessao = cur.fetchone()

        if not sessao:
            cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, 'TRIAGEM')", (telefone,))
            conn.commit()
            estado, nome, cpf, sintoma, horario, ultima_msg = 'TRIAGEM', None, None, None, None, None
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = sessao

        # 2. BLOQUEIO DE DUPLICIDADE (Z-API Delay)
        if msg == ultima_msg:
            return "OK", 200

        # 3. BUSCA VAGAS DISPONÍVEIS
        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_lista = [v[0] for v in cur.fetchall()]
        vagas_txt = ", ".join(vagas_lista) if vagas_lista else "Agenda lotada"

        resposta = ""

        # 4. MÁQUINA DE ESTADOS (O FUNIL)
        if estado == "TRIAGEM":
            sintoma = msg
            estado = "AGENDAMENTO"
            if not vagas_lista:
                resposta = "Olá! No momento nossa agenda está completa, mas posso te colocar na lista de espera. Deseja?"
                estado = "TRIAGEM" # Reseta para não travar
            else:
                resposta = f"Entendi sua necessidade. Para esses sintomas, o ideal é o Clínico Geral. Tenho estes horários: {vagas_txt}. Qual você prefere?"
        
        elif estado == "AGENDAMENTO":
            # Tenta encontrar o horário na mensagem
            h_final = next((v for v in vagas_lista if v in msg or msg.split(':')[0] in v), None)
            
            if not h_final:
                resposta = f"Por favor, escolha um destes horários disponíveis: {vagas_txt}"
            else:
                horario = h_final
                estado = "DADOS_NOME"
                resposta = f"Perfeito, reservado para às {horario}. Agora, qual seu nome completo para a ficha?"
        
        elif estado == "DADOS_NOME":
            nome = msg
            estado = "DADOS_CPF"
            resposta = f"Obrigado, {nome.split()[0]}. Para finalizar, digite apenas os 11 números do seu CPF."
            
        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', msg)
            if len(cpf_limpo) != 11:
                resposta = "O CPF deve ter 11 números. Poderia enviar novamente?"
            else:
                cpf = cpf_limpo
                estado = "CONFIRMADO"
                # Baixa real na agenda (Postgres Safe Update)
                cur.execute("""
                    UPDATE agenda 
                    SET disponivel=FALSE 
                    WHERE id IN (SELECT id FROM agenda WHERE hora=%s AND disponivel=TRUE LIMIT 1)
                """, (horario,))
                resposta = f"Tudo pronto, {nome.split()[0]}! Seu agendamento para {horario} foi confirmado com sucesso. Nossa equipe te aguarda!"
        else:
            resposta = "Seu agendamento já está confirmado. Em breve nossa equipe entrará em contato para os preparativos."

        # 5. ATUALIZA A SESSÃO E SALVA A ÚLTIMA MSG
        cur.execute("""
            UPDATE sessoes 
            SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s 
            WHERE telefone=%s
        """, (estado, nome, cpf, sintoma, horario, msg, telefone))
        
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print(f"❌ ERRO NO PROCESSO: {e}")
    finally:
        if conn: conn.close()
    
    return "OK", 200

# ==========================================
# 🛠️ ROTAS DE SUPORTE (RESET E HOME)
# ==========================================
@app.route('/reset', methods=['GET'])
def reset():
    """Limpa tudo e recarrega as vagas da agenda"""
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
        # Horários de teste
        horarios = ["09:00", "10:30", "14:00", "16:30"]
        for h in horarios:
            cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "✅ RESET COMPLETO: AGENDA E SESSÕES LIMPAS!", 200
    except Exception as e:
        return f"Erro ao resetar: {e}", 500
    finally:
        if conn: conn.close()

@app.route('/', methods=['GET'])
def home():
    return "🚀 AGENTE V6.2 OPERACIONAL - IMPÉRIO DE SILÍCIO", 200

# ==========================================
# 🚀 INICIALIZAÇÃO DO SERVIDOR
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
