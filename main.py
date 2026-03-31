# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V22 — AGENTE DE ELITE PREMIUM
# ESCUDO LGPD TURBINADO E TRAVA ANTI-REPETIÇÃO
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V22 - ELITE PREMIUM ATIVO")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DO CLIENTE (CLÍNICA)
# =========================
NOME_CLINICA = os.environ.get("NOME_CLINICA", "Império Saúde").strip()
NOME_ATENDENTE = os.environ.get("NOME_ATENDENTE", "Ana").strip()
TIPO_CLINICA = os.environ.get("TIPO_CLINICA", "AMBOS").strip().upper()

# =========================
# CONFIGURAÇÕES DE SISTEMA
# =========================
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ZAPI_INSTANCE = os.environ.get("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def conectar():
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def init_db():
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                telefone TEXT PRIMARY KEY, estado TEXT, nome TEXT, 
                cpf TEXT, sintoma TEXT, horario TEXT, ultima_msg TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                id SERIAL PRIMARY KEY, hora TEXT, disponivel BOOLEAN DEFAULT TRUE
            )
        """)
        conn.commit()
    except Exception as e:
        print("Erro DB:", e)
    finally:
        if conn: conn.close()

init_db()

def enviar_whatsapp(telefone, mensagem):
    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
    except Exception as e:
        print("Erro WhatsApp:", e)

# =========================
# 🧠 CÉREBRO DE IA (MOTOR GPT-4o LAPIDADO)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, sintoma_atual, horario_atual):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    contexto = f"Sintoma/Especialidade: '{sintoma_atual}'. Horário: '{horario_atual}'." if sintoma_atual else "Ainda não sabemos o sintoma."
    
    mapa_objetivos = {
        "TRIAGEM": "Descobrir o SINTOMA CLARO ou a ESPECIALIDADE (Ex: cardiologista, dor nas costas). Se disser apenas 'consulta' ou 'exame', exija saber o sintoma.",
        "FORMA_PAGAMENTO": "Descobrir se o pagamento será Particular ou por Plano de Saúde.",
        "AGENDAMENTO": f"Fazer o paciente escolher APENAS UM destes horários: {vagas_txt}.",
        "DADOS_NOME": "Coletar o NOME COMPLETO do paciente. Aceite o nome fornecido e avance.",
        "DADOS_CPF": "Coletar o CPF (11 números)."
    }
    objetivo_atual = mapa_objetivos.get(estado_atual, "Avançar no atendimento.")

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, Concierge de Saúde premium da {NOME_CLINICA}.
ESTADO DO FUNIL: {estado_atual}
O QUE VOCÊ PRECISA EXTRAIR AGORA: {objetivo_atual}

Contexto: {contexto}
Mensagem do paciente: "{mensagem_paciente}"

🛡️ REGRAS INQUEBRÁVEIS (OBRIGATÓRIO):
1. RESPONDER DÚVIDAS CLARAS: Se o paciente fizer uma pergunta direta (ex: "qual especialista?"), responda. MAS se ele apenas der uma resposta errada (ex: nome inválido), NÃO repita informações antigas de outras etapas. Apenas corrija e exija o dado da etapa atual.
2. INDICAÇÃO X DIAGNÓSTICO: Pode indicar o especialista para um sintoma, mas NUNCA dê diagnóstico.
3. PROIBIDO INVENTAR: Nunca sugira pular etapas.
4. PALAVRAS PROIBIDAS (RISCO MÁXIMO): NUNCA use "Entendo", "Compreendo", "Desculpe", "Lamento" ou "Sinto muito". Seja ágil e resolutivo.
5. DISCRIÇÃO: Nunca repita a doença do paciente explicitamente na sua resposta.

Retorne APENAS um JSON válido:
{{
    "forneceu_dado_correto": true ou false (true se a mensagem for a resposta da sua missão atual. false se for pergunta ou dado inválido),
    "resposta_concierge": "Se false, tire a dúvida ou corrija o erro com classe, e EXIJA o dado da etapa atual sem repetir assuntos antigos. (Vazio se true)",
    "dado_extraido": "O dado purificado que ele passou ou null"
}}"""

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": prompt_sistema}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return {"forneceu_dado_correto": True, "resposta_concierge": "", "dado_extraido": mensagem_paciente}

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

        # 1. BOAS-VINDAS
        if not row:
            estado, nome, cpf, sintoma, horario, ultima_msg = "TRIAGEM", None, None, None, None, msg_clean
            cur.execute("INSERT INTO sessoes (telefone, estado, ultima_msg) VALUES (%s, %s, %s)", (telefone, estado, ultima_msg))
            conn.commit()
            resposta = f"Olá! Sou a {NOME_ATENDENTE}, concierge digital da {NOME_CLINICA}. Como posso cuidar da sua saúde hoje?"
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        vagas_lista = [v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in raw_vagas if v[0]]
        vagas_txt = ", ".join(vagas_lista) if vagas_lista else ""

        # 2. ESCUDOS
        gatilhos_emergencia = ["passando mal", "infartando", "dor no peito", "explodir", "socorro", "morrendo", "acidente", "sangrando"]
        if any(p in msg_lower for p in gatilhos_emergencia):
            resposta = "🚨 *ATENÇÃO:* Este é um canal exclusivamente administrativo e não realiza pronto-atendimento. Ligue imediatamente para o *SAMU (192)*."
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        if any(p in msg_lower for p in ["início", "inicio", "recomeçar", "voltar do zero", "cancelar tudo"]) and estado != "TRIAGEM":
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            resposta = "Feito. Cancelei o processo anterior. Qual é exatamente o sintoma ou especialidade para começarmos?"
            cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
            
        # --- O NOVO ESCUDO LGPD TURBINADO ---
        recusa_cpf = ["não vou", "nao vou", "não posso", "nao posso", "não quero", "recuso", "recepção", "recepcao", "pessoalmente", "presencialmente", "na hora", "na clinica", "na clínica"]
        if estado == "DADOS_CPF" and any(p in msg_lower for p in recusa_cpf):
            cpf, estado = "FORNECIDO_NA_RECEPÇÃO", "CONFIRMADO"
            cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
            resposta = f"Totalmente compreensível. Mantive sua reserva para as {horario}. Você pode fornecer o documento na recepção ao chegar. Agendamento 100% confirmado! Deseja marcar para mais alguém?"
            cur.execute("UPDATE sessoes SET estado=%s, cpf=%s, ultima_msg=%s WHERE telefone=%s", (estado, cpf, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        if estado == "CONFIRMADO":
            if any(p in msg_lower for p in ["sim", "ssim", "quero", "pessoas", "pessoa", "mais", "marcar"]):
                estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
                resposta = "Excelente! Qual é a especialidade ou o sintoma desta nova pessoa?"
                cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
                conn.commit()
                enviar_whatsapp(telefone, resposta)
                return "OK", 200
            elif any(p in msg_lower for p in ["não", "nao", "obrigado", "tchau", "valeu"]):
                resposta = f"A {NOME_CLINICA} agradece a confiança. Um excelente dia!"
                enviar_whatsapp(telefone, resposta)
                return "OK", 200
            elif any(p in msg_lower for p in ["errado", "erro", "mudar", "alterar", "cancelar", "especialista", "reclamar"]):
                estado, nome, cpf, sintoma = "TRIAGEM", None, None, None
                cur.execute("UPDATE agenda SET disponivel=TRUE WHERE hora=%s", (horario,))
                horario = None
                resposta = "Vamos corrigir isso imediatamente. Cancelei a reserva. Por favor, me informe qual é a especialidade correta que você precisa."
                cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
                conn.commit()
                enviar_whatsapp(telefone, resposta)
                return "OK", 200
            elif any(p in msg_lower for p in ["oi", "ola", "olá", "bom dia", "boa tarde"]):
                estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
                resposta = f"Olá novamente! Aqui é a {NOME_ATENDENTE} da {NOME_CLINICA}. Como posso te ajudar com a sua saúde hoje?"
                cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, telefone))
                conn.commit()
                enviar_whatsapp(telefone, resposta)
                return "OK", 200
            else:
                resposta = f"Seu agendamento para as {horario} está garantido na clínica. Se precisar de algo, é só me chamar."
                enviar_whatsapp(telefone, resposta)
                return "OK", 200

        # 3. AVALIAÇÃO DO CÉREBRO
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, sintoma, horario)
        
        if not analise.get("forneceu_dado_correto"):
            resposta = analise.get("resposta_concierge", "Por favor, seja mais específico na resposta.")
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
        
        dado_extraido = analise.get("dado_extraido")
        dado_limpo = str(dado_extraido) if dado_extraido is not None else msg_clean
        resposta = ""

        # 4. PROGRESSÃO DO FUNIL
        if estado == "TRIAGEM":
            sintoma = dado_limpo
            if TIPO_CLINICA == "AMBOS":
                estado = "FORMA_PAGAMENTO"
                resposta = "Certo. O atendimento será particular ou através de plano de saúde?"
            elif TIPO_CLINICA == "PLANO":
                estado = "FORMA_PAGAMENTO"
                resposta = "Certo. Para adiantarmos a liberação, qual é o seu convênio médico?"
            else:
                estado = "AGENDAMENTO"
                if not vagas_lista:
                    resposta = "Nossa agenda particular de hoje já está completa. Gostaria de entrar na lista de espera?"
                    estado = "LISTA_ESPERA"
                else:
                    resposta = f"Nossos atendimentos são particulares. Os horários livres hoje são: {vagas_txt}. Qual prefere?"

        elif estado == "FORMA_PAGAMENTO":
            sintoma = f"{sintoma} | Pagamento: {dado_limpo}"
            estado = "AGENDAMENTO"
            if not vagas_lista:
                resposta = "Nossa agenda para hoje já está completa. Gostaria de entrar na lista de espera?"
                estado = "LISTA_ESPERA"
            else:
                resposta = f"Perfeito. Nossos horários livres hoje são: {vagas_txt}. Qual deles fica melhor na sua rotina?"

        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', dado_limpo)
            if match:
                h_dig = match.group(1).zfill(2)
                h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
                if h_final:
                    horario, estado = h_final, "DADOS_NOME"
                    resposta = f"Ótimo. O horário das {horario} está reservado. Qual é o nome completo do paciente?"
                else:
                    resposta = f"Esse horário específico não temos mais hoje. Por favor, escolha entre: {vagas_txt}."
            else:
                resposta = f"Para garantirmos logo a sua vaga, me confirme o número do horário desejado: {vagas_txt}"

        elif estado == "DADOS_NOME":
            nome, estado = dado_limpo, "DADOS_CPF"
            primeiro_nome = nome.split()[0] if nome else "Paciente"
            resposta = f"Muito prazer, {primeiro_nome}. Para criarmos sua ficha com segurança, digite apenas os 11 números do seu CPF (ou avise se preferir informar na recepção)."

        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', dado_limpo)
            if len(cpf_limpo) != 11:
                resposta = "O CPF parece incompleto. Poderia digitar os 11 números novamente para a validação?"
            else:
                cpf, estado = "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Tudo pronto! Agendamento para as {horario} 100% confirmado. Quer aproveitar e marcar para mais alguém?"

        elif estado == "LISTA_ESPERA":
            if any(p in dado_limpo.lower() for p in ["sim", "quero", "pode", "ok"]):
                estado, resposta = "CONFIRMADO", "Feito. Você está na lista de espera. Entraremos em contato assim que vagar um horário!"
            else:
                estado, resposta = "TRIAGEM", "Tranquilo. Caso precise de algo mais, estou à disposição."

        # SALVAR ESTADO
        cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
        conn.commit()
        enviar_whatsapp(telefone, resposta)

    except Exception as e:
        print("Erro Webhook:", e)
    finally:
        if conn: conn.close()
    return "OK", 200

@app.route('/reset', methods=['GET'])
def reset():
    conn = None
    try:
        conn = conectar(); cur = conn.cursor()
        cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
        for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
        conn.commit()
        return "✅ RESET V22 OK", 200
    except Exception as e: return str(e), 500
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 IMPÉRIO DE SILÍCIO V22 (ELITE PREMIUM) ATIVO", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
