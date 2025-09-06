import os
import json           
import unicodedata
import requests
from dataclasses import dataclass
from functools import lru_cache

OPENAI = "openai"
HF = "huggingface"
LOCAL = "local"

PROVIDER = os.getenv("PROVIDER", LOCAL).lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
HF_ZEROSHOT_MODEL = os.getenv("HF_ZEROSHOT_MODEL", "facebook/bart-large-mnli")
HF_GENERATION_MODEL = os.getenv("HF_GENERATION_MODEL", "google/flan-t5-large")

CATEGORIES = ["Produtivo", "Improdutivo"]
INTENTS = ["STATUS","ATTACHMENT","ACCESS","ERROR","CLOSURE","THANKS","GREETINGS","SUPPORT","OTHER"]

@lru_cache(maxsize=256)
def _memo_key(text, provider, model):
    return text.strip(), provider, model

@dataclass
class AIClassifyResult:
    ok: bool
    category: str
    intent: str
    confidence: float
    raw: dict

def _sanitize_label(label: str, allowed: list[str], default: str) -> str:
    if not label:
        return default
    up = label.strip().upper()
    for a in allowed:
        if up == a.upper():
            return a
    aliases = {
        "PRODUCTIVE": "Produtivo",
        "UNPRODUCTIVE": "Improdutivo",
        "ATTACH": "ATTACHMENT",
        "ATTACHMENT/DOCUMENT": "ATTACHMENT",
        "GREETING": "GREETINGS",
        "SUPPORT": "SUPORTE",
        "THANK": "THANKS",
    }
    return aliases.get(up, default)

# -------------------- OpenAI --------------------
def _openai_classify_and_intent(text: str) -> AIClassifyResult:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    system = (
        "Você classifica e-mails corporativos. Saudações NÃO anulam pedidos de ação.\n"
        "Responda APENAS em JSON "
        "{\"category\":\"Produtivo|Improdutivo\",\"intent\":\"STATUS|ATTACHMENT|ACCESS|ERROR|CLOSURE|THANKS|GREETINGS|SUPPORT|OTHER\",\"confidence\":0..1}."
    )
    user = f"""
        Regras:
        - Se houver saudação + pedido de ação (status, acesso, erro etc.), PRIORIZE a ação (Produtivo).
        Exemplos:
        - "Bom dia, poderiam informar o status do chamado 123?" -> {{"category":"Produtivo","intent":"STATUS","confidence":0.95}}
        - "Segue comprovante em anexo, podem confirmar?" -> {{"category":"Produtivo","intent":"ATTACHMENT","confidence":0.95}}
        - "Não consigo acessar o portal, podem desbloquear?" -> {{"category":"Produtivo","intent":"ACCESS","confidence":0.95}}
        - "Obrigado, era só isso mesmo." -> {{"category":"Improdutivo","intent":"THANKS","confidence":0.95}}

        Email:
        {text}
        """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
    )

    content = resp.choices[0].message.content.strip()
    data = {}
    try:
        data = json.loads(content)
    except Exception:
        data = {}

    cat = (data.get("category") or "").strip().title()
    if cat not in CATEGORIES:
        cat = "Produtivo"
    intent = (data.get("intent") or "").strip().upper()
    if intent not in INTENTS:
        intent = "OTHER"
    conf = float(data.get("confidence", 0.6))
    return AIClassifyResult(True, cat, intent, conf, {"openai_raw": data})

def _openai_generate_reply(text: str, category: str, intent: str, lang: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        tone_pt = "Use tom corporativo, objetivo e cordial. Retorne APENAS o corpo do e-mail."
        tone_en = "Use a corporate, concise and polite tone. Return ONLY the email body."
        instructions_pt = {
            "STATUS":"Informe que estamos verificando o status e retornaremos em breve. Peça ticket/logs se necessário.",
            "ATTACHMENT":"Confirme recebimento do arquivo e diga que será avaliado com próximos passos.",
            "ACCESS":"Peça e-mail de login e se houve bloqueio; ofereça desbloqueio/reset de senha.",
            "ERROR": "Se o e-mail já mencionar anexos, confirme que foram recebidos e que serão analisados. Caso contrário, solicite passos, horário e prints/logs.",
            "CLOSURE":"Agradeça e confirme encerramento, mantendo-se à disposição.",
            "THANKS":"Agradeça o agradecimento; sem ação.",
            "GREETINGS":"Agradeça os votos/saudações; sem ação.",
            "OTHER":"Confirme recebimento e diga que retornaremos em breve."
        }
        instructions_en = {
            "STATUS":"Say we're checking the status and will get back soon; ask for ticket/logs if needed.",
            "ATTACHMENT":"Confirm file receipt; will review and follow up with next steps.",
            "ACCESS":"Ask for login email and any lockout message; offer unlock/password reset.",
            "ERROR": "If the email already mentions attachments, acknowledge them and confirm analysis. Otherwise, ask for steps, time and logs/screenshots.",
            "CLOSURE":"Thank and confirm closure; stay available.",
            "THANKS":"Thank for the message; no action needed.",
            "GREETINGS":"Thank for the wishes; no action needed.",
            "OTHER":"Confirm receipt; we'll analyze and follow up soon."
        }
        sign_pt = "Atenciosamente,\nEquipe de Suporte"
        sign_en = "Best regards,\nSupport Team"

        prompt = (
            f"E-mail original:\n{text}\n\n"
            f"Categoria: {category}\n"
            f"Subintenção: {intent}\n\n"
            f"Instrução: {(instructions_en if lang=='en' else instructions_pt).get(intent,'OTHER')}\n"
            f"{tone_en if lang=='en' else tone_pt}\n\n"
            f"Assinatura: {(sign_en if lang=='en' else sign_pt)} (anexe ao final)"
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": "Você redige respostas de e-mail."},
                {"role": "user", "content": prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""

# -------------------- Hugging Face --------------------
def _hf_zero_shot(text: str, candidate_labels: list[str]):
    url = f"https://api-inference.huggingface.co/models/{HF_ZEROSHOT_MODEL}"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": text, "parameters": {"candidate_labels": candidate_labels, "multi_label": False}}
    return requests.post(url, headers=headers, json=payload, timeout=5).json()

def _hf_generate(text: str, instruction: str, lang: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{HF_GENERATION_MODEL}"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    prompt = (
        f"Write a professional corporate email reply in {('English' if lang=='en' else 'Portuguese')}.\n"
        f"Instruction: {instruction}\n"
        f"Original:\n{text}\n\nReply:\n"
    )
    out = requests.post(
        url,
        headers=headers,
        json={"inputs": prompt, "parameters": {"max_new_tokens": 140, "temperature": 0.2}},
        timeout=8
    ).json()
    if isinstance(out, list) and out:
        return out[0].get("generated_text", "").split("Reply:", 1)[-1].strip()
    return ""

def _hf_classify_and_intent(text: str) -> AIClassifyResult:
    try:
        cat_labels = ["Produtivo", "Improdutivo"]
        cat_res = _hf_zero_shot(text, cat_labels)
        if "labels" in cat_res and cat_res["labels"]:
            cat = cat_res["labels"][0]
            cat_score = float(cat_res["scores"][0])
        else:
            cat, cat_score = "Produtivo", 0.6

        intent_res = _hf_zero_shot(text, INTENTS)
        if "labels" in intent_res and intent_res["labels"]:
            intent = intent_res["labels"][0]
            intent_score = float(intent_res["scores"][0])
        else:
            intent, intent_score = "OTHER", 0.6

        return AIClassifyResult(
            True,
            _sanitize_label(cat, CATEGORIES, "Produtivo"),
            _sanitize_label(intent, INTENTS, "OTHER"),
            (cat_score + intent_score) / 2.0,
            {"hf_raw": {"cat": cat_res, "intent": intent_res}},
        )
    except Exception as e:
        return AIClassifyResult(False, "", "OTHER", 0.0, {"error": str(e)})

def _hf_generate_reply(text: str, category: str, intent: str, lang: str) -> str:
    try:
        instructions = {
            "STATUS": "We are checking the status and will get back soon; ask for ticket/logs if needed.",
            "ATTACHMENT": "Confirm file receipt and say it will be reviewed; follow up with next steps.",
            "ACCESS": "Ask for login email and whether there is a block message; offer unlock/password reset.",
            "ERROR": "Ask for reproduction steps, time of occurrence, and logs/screenshots.",
            "CLOSURE": "Thank and confirm closure; stay available.",
            "THANKS": "Thank for the message; no action required.",
            "GREETINGS": "Thank for the wishes; no action required.",
            "OTHER": "Confirm receipt and say you will analyze and follow up soon."
        }
        return _hf_generate(text, instructions.get(intent, "OTHER"), lang)
    except Exception:
        return ""

# -------------------- Fastpath por configuração --------------------
_INTENT_CFG = None

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.lower()

def _load_intent_cfg():
    global _INTENT_CFG
    if _INTENT_CFG is None:
        path = os.getenv("INTENT_CFG_PATH", "intents_config.json")
        with open(path, "r", encoding="utf-8") as f:
            _INTENT_CFG = json.load(f)
    return _INTENT_CFG

def fastpath_from_config(text: str):
    """
    Heurística leve baseada em sinônimos do intents_config.json.
    Retorna categoria/intent e uma CONFIANÇA DINÂMICA calculada
    a partir do número de acertos (hits) e do tamanho do texto.
    """
    try:
        cfg = _load_intent_cfg()
    except Exception:
        return None

    t = _norm(text or "")
    if not t:
        return None

    # conta hits por intenção
    hits_by_intent = {}
    for intent, terms in cfg.get("synonyms", {}).items():
        count = 0
        for term in terms:
            if _norm(term) in t:
                count += 1
        if count > 0:
            hits_by_intent[intent] = count

    if not hits_by_intent:
        return None

    best_intents = sorted(
        hits_by_intent.items(),
        key=lambda kv: (-kv[1], cfg.get("priority_order", INTENTS).index(kv[0]) if kv[0] in cfg.get("priority_order", INTENTS) else 999)
    )
    intent, hits = best_intents[0]

    base = 0.55
    conf = base + 0.12 * min(hits, 4)
    n = len(t)
    if 80 <= n <= 800:
        conf += 0.05
    conf = max(0.55, min(conf, 0.95))

    category = "Produtivo" if intent in {"STATUS", "ATTACHMENT", "ACCESS", "ERROR"} else "Improdutivo"
    return {"category": category, "intent": intent, "confidence": float(conf)}


# -------------------- API pública --------------------
def ai_classify(text: str) -> AIClassifyResult:
    hp = fastpath_from_config(text)
    if hp:
        return AIClassifyResult(True, hp["category"], hp["intent"], hp["confidence"], {"source":"fastpath"})

    #Provedor de IA (se configurado)
    if PROVIDER == OPENAI and OPENAI_API_KEY:
        try:
            return _openai_classify_and_intent(text)
        except Exception as e:
            return AIClassifyResult(False, "", "OTHER", 0.0, {"error": str(e)})

    if PROVIDER == HF and HUGGINGFACE_API_KEY:
        try:
            return _hf_classify_and_intent(text)
        except Exception as e:
            return AIClassifyResult(False, "", "OTHER", 0.0, {"error": str(e)})

    #Sem IA: fallback local (feito em email.py)
    return AIClassifyResult(False, "", "OTHER", 0.0, {})

def ai_generate_reply(text: str, category: str, intent: str, lang: str) -> str:
    if PROVIDER == OPENAI and OPENAI_API_KEY:
        try:
            return _openai_generate_reply(text, category, intent, lang)
        except Exception:
            pass
    if PROVIDER == HF and HUGGINGFACE_API_KEY:
        try:
            return _hf_generate_reply(text, category, intent, lang)
        except Exception:
            pass
    return "" 
