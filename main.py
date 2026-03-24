
@app.route('/webhook', methods=['POST'])
def webhook():
    dados = request.get_json()
    if not dados: return "Sem dados", 200

    # 1. SEGURANÇA: Só responde se for mensagem RECEBIDA (não a que o robô envia)
    if dados.get("fromMe") is True: 
        return "Ignorado: Mensagem própria", 200

    remote_jid = dados.get("phone", "")
    # Tratando diferentes formatos de entrada da Z-API
    message_text = ""
    if "text" in dados and "message" in dados["text"]:
        message_text = dados["text"]["message"]
    elif "momentsMessage" in dados: # Caso seja outro formato de msg
        message_text = dados.get("text", {}).get("message", "")

    if not remote_jid or not message_text: 
        return "Sem conteúdo para processar", 200

    clean_phone = remote_jid.split("@")[0]
    print(f"📩 MÉDICO VIRTUAL: Processando msg de {clean_phone}")

    try:
        # 2. CONFIGURANDO A AUTORIDADE DO ESPECIALISTA
        headers_openai = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
        payload_openai = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system", 
                    "content": (
                        "Você é o Agente de Elite de Atendimento Clínico. "
                        "Sua postura é: Sério, Empático, Altamente Profissional e Focado em Saúde. "
                        "Regra de Ouro: Sua missão é transformar dúvidas em AGENDAMENTOS. "
                        "Se o cliente fugir do assunto (ex: dinheiro, piadas), você deve dizer: "
                        "'Compreendo, mas meu foco aqui é garantir sua saúde e o melhor atendimento na nossa clínica. "
                        "Como posso te ajudar com sua consulta hoje?' "
                        "Nunca responda mais de 3 frases. Seja direto."
                    )
                },
                {"role": "user", "content": message_text}
            ]
        }
        
        # Chamada para OpenAI
        res_ai = requests.post("https://api.openai.com/v1/chat/completions", json=payload_openai, headers=headers_openai)
        
        # LOG PARA DEBUG (Ver no Render se a OpenAI respondeu)
        if res_ai.status_code != 200:
            print(f"❌ ERRO OPENAI: {res_ai.text}")
            return "Erro na IA", 200
            
        resposta_ai = res_ai.json()['choices'][0]['message']['content']

        # 3. ENVIO PARA Z-API (Com tratamento de erro)
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        headers_zapi = {
            "Content-Type": "application/json",
            "Client-Token": ZAPI_CLIENT_TOKEN
        }
        payload_zapi = {
            "phone": clean_phone,
            "message": resposta_ai
        }
        
        envio = requests.post(url_zapi, json=payload_zapi, headers=headers_zapi)
        print(f"✅ STATUS ENVIO Z-API: {envio.status_code}")

    except Exception as e:
        print(f"⚠️ FALHA CRÍTICA NO CÓDIGO: {e}")

    return "OK", 200
