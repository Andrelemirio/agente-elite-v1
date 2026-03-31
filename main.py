# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V15 — AGENTE DE ELITE FINAL
# SEGURANÇA MÉDICA, LGPD E CÉREBRO GPT-4o-MINI
# ============================================

import os
import requests
import psycopg2
import re
import json
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V15 - BLINDAGEM MÁXIMA ATIVA")

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
# CÉREBRO DE IA (OPENAI - GPT-4o-mini)
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, sintoma_atual, horario_atual):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    contexto = f"Sintoma/Especialidade atual: '{sintoma_atual}'. Horário reservado: '{horario_atual}'." if sintoma_atual else "Ainda não sabemos o sintoma."
    
    prompt_sistema = f"""Você é um Concierge de Saúde de altíssimo padrão em uma clínica premium. Seu tom é humano, direto, elegante e empático. NUNCA pareça um robô.
Estamos na etapa de coletar: {estado_atual}.
{contexto}
Vagas de hoje: {vagas_txt}.

Mensagem do paciente: "{mensagem_paciente}".

REGRAS DE OURO:
1. PROIBIDO usar clichês de telemarketing como: "Entendo sua dúvida", "Sinto muito", "Compreendo perfeitamente", "Por favor, me forneça seu CPF".
2. Se o paciente fizer uma pergunta FORA da clínica (ex: investimentos, dicas gerais), corte o assunto com muita elegância, lembrando que você é o Concierge da clínica.
3. Se ele perguntar sobre o médico, use o 'Sintoma/Especialidade atual' para responder.
4. Responda a dúvida de forma breve e natural, e termine a frase conduzindo a conversa de volta para coletar o dado ({estado_atual}).

Retorne APENAS um JSON válido:
{{
    "forneceu_dado_correto": true ou false (true apenas se a mensagem principal dele responder à etapa atual. false se ele fez uma pergunta ou mudou de assunto),
    "resposta_concierge": "Sua resposta super humana tirando a dúvida e retomando o fluxo. (vazio se true)",
    "dado_extraido": "O dado que ele passou (ex: nome, horário, CPF) ou null"
}}"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": prompt_sistema}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
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

        if not row:
            estado, nome, cpf, sintoma, horario, ultima_msg = "TRIAGEM", None, None, None, None, None
            cur.execute("INSERT INTO sessoes (telefone, estado) VALUES (%s, %s)", (telefone, estado))
            conn.commit()
        else:
            estado, nome, cpf, sintoma, horario, ultima_msg = row

        if msg_clean == ultima_msg: return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        raw_vagas = cur.fetchall()
        vagas_lista = [v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in raw_vagas if v[0]]
        vagas_txt = ", ".join(vagas_lista) if vagas_lista else ""

        # ==========================================
        # 🛡️ CAMADA 1: BLINDAGENS DE SEGURANÇA NATIVAS
        # ==========================================

        # 1. EMERGÊNCIA MÉDICA (CRÍTICO)
        gatilhos_emergencia = ["passando mal", "infartando", "dor no peito", "explodir", "socorro", "morrendo", "muita dor", "coração doendo"]
        if any(p in msg_lower for p in gatilhos_emergencia):
            resposta = "🚨 *ATENÇÃO:* Identifiquei que você está relatando uma urgência médica grave. Por favor, não aguarde atendimento por aqui. Dirija-se imediatamente ao Pronto Socorro mais próximo ou ligue agora para o *SAMU (192)*. A sua vida em primeiro lugar."
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        # 2. OVERRIDE GLOBAL (Recomeçar)
        if any(p in msg_lower for p in ["início", "inicio", "recomeçar", "voltar do zero", "cancelar tudo"]) and estado != "TRIAGEM":
            estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
            resposta = "Feito. Cancelei o atendimento anterior. Como posso te ajudar agora? Qual é o sintoma ou especialidade?"
            cur.execute("UPDATE sessoes SET estado=%s, nome=%s, cpf=%s, sintoma=%s, horario=%s, ultima_msg=%s WHERE telefone=%s", (estado, nome, cpf, sintoma, horario, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        # 3. PAUSA HUMANA
        if any(p in msg_lower for p in ["espera", "aguarda", "um momento", "vou procurar", "vou pegar", "ja volto", "já volto"]):
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, "Sem pressa, faça no seu tempo. Fico aguardando você me chamar.")
            return "OK", 200

        # 4. RECUSA DE CPF (LGPD)
        recusa_cpf = ["não vou", "nao vou", "não posso", "nao posso", "não quero", "não vou passar", "recuso"]
        if estado == "DADOS_CPF" and any(p in msg_lower for p in recusa_cpf):
            cpf, estado = "RECUSADO_LGPD", "CONFIRMADO"
            cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
            resposta = f"Totalmente compreensível. Sem problemas! Mantive sua reserva para as {horario}. Você pode fornecer o documento diretamente na recepção quando chegar. Agendamento confirmado! Deseja marcar para mais alguém?"
            cur.execute("UPDATE sessoes SET estado=%s, cpf=%s, ultima_msg=%s WHERE telefone=%s", (estado, cpf, msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200

        # ==========================================
        # 🧠 CAMADA 2: ANÁLISE NEURAL (IA)
        # ==========================================
        analise = analisar_com_ia(msg_clean, estado, vagas_txt, sintoma, horario)
        
        if not analise.get("forneceu_dado_correto"):
            resposta = analise.get("resposta_concierge", "Pode repetir, por favor?")
            cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
            conn.commit()
            enviar_whatsapp(telefone, resposta)
            return "OK", 200
        
        dado_limpo = str(analise.get("dado_extraido", msg_clean))
        resposta = ""

        # ==========================================
        # ⚙️ CAMADA 3: MOTOR DE FLUXO SEGURO
        # ==========================================
        if estado == "TRIAGEM":
            sintoma = dado_limpo
            estado = "AGENDAMENTO"
            if not vagas_lista:
                resposta = "Nossa agenda para hoje já está completa. Gostaria que eu adicionasse o paciente na nossa lista de espera prioritária?"
                estado = "LISTA_ESPERA"
            else:
                resposta = f"Certo, já registrei a necessidade. Nossos horários livres hoje são: {vagas_txt}. Qual deles fica melhor na sua rotina?"

        elif estado == "AGENDAMENTO":
            match = re.search(r'(\d{1,2})', dado_limpo)
            if match:
                h_dig = match.group(1).zfill(2)
                h_final = next((v for v in vagas_lista if v.startswith(h_dig)), None)
                if h_final:
                    horario, estado = h_final, "DADOS_NOME"
                    resposta = f"Perfeito. O horário das {horario} já está reservado para você. Qual é o nome completo do paciente?"
                else:
                    resposta = f"Esse horário específico não temos mais hoje. Por favor, escolha entre: {vagas_txt}."
            else:
                resposta = f"Para garantir logo a sua vaga, me confirme apenas o número do horário desejado: {vagas_txt}"

        elif estado == "DADOS_NOME":
            nome, estado = dado_limpo, "DADOS_CPF"
            primeiro_nome = nome.split()[0] if nome else "Paciente"
            resposta = f"Muito prazer, {primeiro_nome}. Para criarmos sua ficha com segurança, digite apenas os 11 números do seu CPF (ou me avise se preferir dar na recepção)."

        elif estado == "DADOS_CPF":
            cpf_limpo = re.sub(r'\D', '', dado_limpo)
            if len(cpf_limpo) != 11:
                resposta = "O CPF parece incompleto. Poderia digitar os 11 números novamente para eu validar?"
            else:
                cpf, estado = cpf_limpo, "CONFIRMADO"
                cur.execute("UPDATE agenda SET disponivel=FALSE WHERE id IN (SELECT id FROM agenda WHERE CAST(hora AS TEXT) LIKE %s AND disponivel=TRUE LIMIT 1)", (f"{horario}%",))
                resposta = f"Tudo pronto! Agendamento para as {horario} 100% confirmado na clínica. Quer aproveitar e marcar para mais alguém?"

        elif estado == "CONFIRMADO":
            if any(p in dado_limpo.lower() for p in ["sim", "quero", "pessoas", "pessoa", "mais", "ok", "pode"]):
                estado, nome, cpf, sintoma, horario = "TRIAGEM", None, None, None, None
                resposta = "Excelente! Vamos iniciar o novo agendamento. Qual é a especialidade ou o sintoma desta pessoa?"
            else:
                resposta = "Maravilha. A equipe agradece a confiança e aguarda vocês. Um excelente dia!"

        elif estado == "LISTA_ESPERA":
            if any(p in dado_limpo.lower() for p in ["sim", "quero", "pode", "ok"]):
                estado, resposta = "CONFIRMADO", "Feito. Você está na lista de espera. Entraremos em contato no segundo que vagar um horário!"
            else:
                estado, resposta = "TRIAGEM", "Tranquilo. Caso precise de algo mais, estou aqui."

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
        return "✅ RESET V15 OK", 200
    except Exception as e: return str(e), 500
    finally:
        if conn: conn.close()

@app.route('/')
def home(): return "🚀 IMPÉRIO DE SILÍCIO V15 (AGENTE DE ELITE) ATIVO", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
