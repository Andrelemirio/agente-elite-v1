# ============================================
# 🚀 IMPÉRIO DE SILÍCIO V43 — ODONTO SILÍCIO (AGENTE DE ELITE)
# VISÃO, WHISPER E TRAVA DE ASSINCRONISMO (ANTI-DUPLICAÇÃO)
# ============================================

import os
import requests
import psycopg2
import json
import re
import time
import random
import threading
from flask import Flask, request

print("🚀 IMPÉRIO DE SILÍCIO V43 - AGENTE DE ELITE (ASSÍNCRONO E MULTIMODAL)")

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DO CLIENTE
# =========================
NOME_CLINICA = os.environ.get("NOME_CLINICA", "Odonto Silício").strip()
NOME_ATENDENTE = os.environ.get("NOME_ATENDENTE", "Ana").strip()

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
        conn = conectar(); cur = conn.cursor()
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
    except Exception as e: print("Erro DB:", e)
    finally:
        if conn: conn.close()

init_db()

# --- TRAVA 1: DELAY ANTI-BAN EM SEGUNDO PLANO ---
def enviar_whatsapp(telefone, mensagem):
    try:
        url_presence = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-presence"
        requests.post(url_presence, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "presence": "composing"}, timeout=5)
        
        time.sleep(random.randint(2, 4))
        
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        requests.post(url, headers={"Client-Token": ZAPI_CLIENT_TOKEN}, json={"phone": telefone, "message": mensagem}, timeout=10)
    except Exception as e: print("Erro WhatsApp:", e)

# --- MÓDULO DE AUDIÇÃO: INTEGRAÇÃO WHISPER ---
def transcrever_audio(audio_url):
    try:
        resposta_audio = requests.get(audio_url, timeout=15)
        if resposta_audio.status_code != 200: return None
        
        caminho_temp = f"/tmp/audio_paciente_{random.randint(1000,9999)}.ogg"
        with open(caminho_temp, 'wb') as f:
            f.write(resposta_audio.content)
        
        url_whisper = "https://api.openai.com/v1/audio/transcriptions"
        headers_whisper = {"Authorization": f"Bearer {OPENAI_KEY}"}
        
        with open(caminho_temp, 'rb') as arquivo_audio:
            files = {
                "file": ("audio.ogg", arquivo_audio, "audio/ogg"),
                "model": (None, "whisper-1"),
                "language": (None, "pt")
            }
            res_whisper = requests.post(url_whisper, headers=headers_whisper, files=files, timeout=20)
        
        if os.path.exists(caminho_temp): os.remove(caminho_temp)
            
        if res_whisper.status_code == 200:
            return res_whisper.json().get("text", "")
        return None
    except Exception as e:
        print("Erro no Whisper:", e)
        return None

# =========================
# 🧠 CÉREBRO GPT-4o SÊNIOR
# =========================
def analisar_com_ia(mensagem_paciente, estado_atual, vagas_txt, dados_acumulados, media_url=None):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    
    instrucoes = {
        "TRIAGEM": "AÇÃO: Identifique o procedimento. Diga que agendará uma avaliação. FECHAMENTO: Pergunte se é PRIMEIRA VEZ na clínica. (novo_estado: STATUS_CONSULTA)",
        "STATUS_CONSULTA": "AÇÃO: Agradeça. FECHAMENTO: Pergunte se a consulta será PARTICULAR ou pelo PLANO de saúde. (novo_estado: FORMA_PAGAMENTO)",
        "FORMA_PAGAMENTO": f"AÇÃO: Ofereça APENAS os horários {vagas_txt}. FECHAMENTO: Pergunte 'Qual desses horários fica melhor para você?' (novo_estado: AGENDAMENTO)",
        "AGENDAMENTO": f"AÇÃO: SE o paciente escolheu um horário, confirme. FECHAMENTO: Peça o NOME COMPLETO (novo_estado: DADOS_NOME). SE não escolheu, ofereça os horários novamente (novo_estado: AGENDAMENTO).",
        "DADOS_NOME": "AÇÃO: SE o paciente forneceu o nome, avise que o resto dos dados pode ser dado na recepção. FECHAMENTO: Peça o CPF para o cadastro base (novo_estado: DADOS_CPF). SE não, continue pedindo o nome (novo_estado: DADOS_NOME).",
        "DADOS_CPF": "AÇÃO: Confirme que o horário está reservado. FECHAMENTO: Pergunte se há mais alguém para agendar ou se ficou alguma dúvida. (novo_estado: CONFIRMADO)",
        "CONFIRMADO": "AÇÃO: SE o paciente disser NÃO, OBRIGADO, ou se despedir, encerre sem perguntas (novo_estado: ENCERRADO).",
        "ENCERRADO": "AÇÃO: O atendimento acabou. Apenas seja educado, NÃO faça perguntas, NÃO puxe assunto. (novo_estado: ENCERRADO)"
    }
    
    instrucao_atual = instrucoes.get(estado_atual, "AÇÃO: Conduza para o agendamento.")

    prompt_sistema = f"""Você é {NOME_ATENDENTE}, a Concierge de Elite da clínica {NOME_CLINICA}.

DADOS DO PACIENTE: {dados_acumulados}
ESTADO ATUAL DO SISTEMA: {estado_atual}
HORÁRIOS DISPONÍVEIS: {vagas_txt}

REGRAS DE OURO DA BLINDAGEM (OBRIGATÓRIO):
1. CONTROLE DE FLUXO: NUNCA mande uma mensagem sem uma pergunta no final, exceto no estado ENCERRADO. Você lidera a conversa.
2. FUGA DE ASSUNTO: Se o paciente falar sobre política, esportes, clima, culinária ou qualquer coisa fora da odontologia, CORTE IMEDIATAMENTE e educadamente.
3. LIMITES MÉDICOS E VISUAIS: Se o paciente enviar uma IMAGEM, diga o que você está vendo, mas alerte que "apenas o dentista pode dar um diagnóstico final na avaliação presencial".
4. FIDELIDADE DE DADOS: NUNCA altere ou questione um horário que já esteja definido nos "DADOS DO PACIENTE". Confie no histórico.

SUA MISSÃO EXATA AGORA:
{instrucao_atual}

Retorne APENAS um JSON:
{{
    "resposta_para_paciente": "Sua resposta natural e persuasiva",
    "novo_estado": "O estado exato após sua análise",
    "resumo_dados": "Mantenha o histórico atualizado"
}}"""

    if media_url:
        conteudo_usuario = [{"type": "text", "text": mensagem_paciente}, {"type": "image_url", "image_url": {"url": media_url}}]
    else:
        conteudo_usuario = mensagem_paciente

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": conteudo_usuario}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        return json.loads(res.json()['choices'][0]['message']['content'])
    except: return None

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.route('/webhook', methods=['POST'])
def webhook():
    conn = None
    try:
        data = request.get_json(force=True)
        if not data or data.get("fromMe"): return "OK", 200
        
        telefone = data.get("phone", "").split("@")[0]
        
        media_url = None
        if "audio" in data and "audioUrl" in data["audio"]:
            audio_url = data["audio"]["audioUrl"]
            transcricao = transcrever_audio(audio_url)
            if transcricao:
                msg = f"🎤 [ÁUDIO TRANSCRITO]: {transcricao}"
            else:
                msg = f"🎤 [FALHA NO ÁUDIO]: {audio_url[-15:]}"
        elif "image" in data and "imageUrl" in data["image"]:
            media_url = data["image"]["imageUrl"]
            msg = f"📸 [IMAGEM RECEBIDA]: {media_url[-20:]} Analise a imagem e conecte com o atendimento."
        else:
            msg = data.get("text", {}).get("message", "") if isinstance(data.get("text"), dict) else str(data.get("message", ""))
        
        msg_clean, msg_lower = msg.strip(), msg.strip().lower()

        if not telefone or not msg_clean: return "OK", 200

        conn = conectar(); cur = conn.cursor()
        cur.execute("SELECT estado, sintoma, ultima_msg FROM sessoes WHERE telefone=%s", (telefone,))
        row = cur.fetchone()

        if not row:
            estado, dados_acumulados = "TRIAGEM", "Nenhum dado ainda."
            cur.execute("INSERT INTO sessoes (telefone, estado, sintoma, ultima_msg) VALUES (%s, %s, %s, %s)", (telefone, estado, dados_acumulados, msg_clean))
            conn.commit()
            threading.Thread(target=enviar_whatsapp, args=(telefone, f"Olá! Seja muito bem-vindo(a) à {NOME_CLINICA}. Meu nome é {NOME_ATENDENTE} e sou a sua concierge digital. Como posso ajudar a cuidar do seu sorriso hoje?")).start()
            return "OK", 200
        else:
            estado, dados_acumulados, ultima_msg = row

        # --- TRAVA DE REPETIÇÃO BLINDADA ---
        if msg_clean == ultima_msg: return "OK", 200

        if estado == "ENCERRADO":
            encerramentos = ["ok", "obrigado", "obrigada", "valeu", "tchau", "ótimo", "perfeito", "joia", "beleza"]
            if any(p in msg_lower for p in encerramentos) or len(msg_clean) <= 10:
                cur.execute("UPDATE sessoes SET ultima_msg=%s WHERE telefone=%s", (msg_clean, telefone))
                conn.commit()
                return "OK", 200

        cur.execute("SELECT hora FROM agenda WHERE disponivel=TRUE ORDER BY hora LIMIT 4")
        vagas_txt = ", ".join([v[0].strftime('%H:%M') if hasattr(v[0], 'strftime') else str(v[0])[:5] for v in cur.fetchall()])

        emergencias = ["dor insuportável", "sangramento forte", "socorro", "dor extrema"]
        if any(p in msg_lower for p in emergencias) and not media_url:
            threading.Thread(target=enviar_whatsapp, args=(telefone, "🚨 Identifiquei sinais de urgência. Para casos de dor extrema ou sangramento forte, dirija-se imediatamente a um pronto atendimento odontológico.")).start()
            return "OK", 200

        analise = analisar_com_ia(msg_clean, estado, vagas_txt, dados_acumulados, media_url)
        if not analise:
            threading.Thread(target=enviar_whatsapp, args=(telefone, "Tivemos uma pequena instabilidade de rede. Você poderia repetir sua última mensagem, por favor?")).start()
            return "OK", 200

        resposta = analise.get("resposta_para_paciente", "Pode me explicar melhor?")
        novo_estado = analise.get("novo_estado", estado)
        novos_dados = analise.get("resumo_dados", dados_acumulados)

        ordem_estados = {"TRIAGEM": 1, "STATUS_CONSULTA": 2, "FORMA_PAGAMENTO": 3, "AGENDAMENTO": 4, "DADOS_NOME": 5, "DADOS_CPF": 6, "CONFIRMADO": 7, "ENCERRADO": 8}
        
        match_horario = re.search(r'\b(9|09|11|14|16)\b', msg_clean)
        if estado in ["FORMA_PAGAMENTO", "AGENDAMENTO"] and match_horario and not media_url:
            hora_formatada = match_horario.group(1).zfill(2) + ":00"
            novo_estado = "DADOS_NOME"
            novos_dados = f"{dados_acumulados} | Horário: {hora_formatada}"
            resposta = f"Perfeito! O horário das {hora_formatada} está reservado. Agora, por favor, poderia me informar o seu nome completo?"

        if novo_estado == "DADOS_NOME" and estado == "AGENDAMENTO":
            if not any(h in novos_dados or h in msg_clean for h in ["09", "11", "14", "16", "9"]):
                novo_estado = "AGENDAMENTO"

        elif estado == "DADOS_CPF" and not media_url:
            if len(re.sub(r'\D', '', msg_clean)) >= 11:
                novo_estado = "CONFIRMADO"
                resposta = "CPF recebido com sucesso! Seu agendamento está confirmado. Há mais alguém da família que deseja agendar ou ficou alguma dúvida?"

        elif ordem_estados.get(novo_estado, 0) < ordem_estados.get(estado, 0):
            if estado == "CONFIRMADO" and novo_estado in ["AGENDAMENTO", "TRIAGEM", "FORMA_PAGAMENTO"]:
                pass
            else:
                novo_estado = estado

        if (novo_estado == "CONFIRMADO" or novo_estado == "ENCERRADO") and estado != "CONFIRMADO" and estado != "ENCERRADO":
            if not any(p in msg_lower for p in ["cancelar", "desisto", "outra"]):
                for h in ["09:00", "11:00", "14:30", "16:00"]:
                    if h in novos_dados or h in msg_clean:
                        cur.execute("UPDATE agenda SET disponivel=FALSE WHERE CAST(hora AS TEXT) LIKE %s", (f"{h}%",))
                        break

        cur.execute("UPDATE sessoes SET estado=%s, sintoma=%s, ultima_msg=%s WHERE telefone=%s", (novo_estado, novos_dados, msg_clean, telefone))
        conn.commit()
        
        # --- O PULO DO GATO: Envia a mensagem em segundo plano! ---
        threading.Thread(target=enviar_whatsapp, args=(telefone, resposta)).start()

    except Exception as e: print("Erro Webhook:", e)
    finally:
        if conn: conn.close()
    return "OK", 200

@app.route('/reset')
def reset():
    conn = conectar(); cur = conn.cursor()
    cur.execute("DELETE FROM agenda; DELETE FROM sessoes;")
    for h in ["09:00", "11:00", "14:30", "16:00"]: cur.execute("INSERT INTO agenda (hora) VALUES (%s)", (h,))
    conn.commit(); conn.close()
    return "✅ RESET ODONTO SILÍCIO OK"

@app.route('/')
def home(): return "🚀 ODONTO SILÍCIO V43 ATIVA (BLINDADA CONTRA REPETIÇÕES)"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
