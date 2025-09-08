import os
import json
import unicodedata
import requests
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional

# -------------------- Constantes / ENV --------------------
OPENAI = "openai"
HF     = "huggingface"
LOCAL  = "local"

PROVIDER = os.getenv("PROVIDER", LOCAL).lower()

OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY")
HUGGINGFACE_API_KEY  = os.getenv("HUGGINGFACE_API_KEY")
HF_ZEROSHOT_MODEL    = os.getenv("HF_ZEROSHOT_MODEL", "facebook/bart-large-mnli")
HF_GENERATION_MODEL  = os.getenv("HF_GENERATION_MODEL", "google/flan-t5-base")
FORCE_API_CLASSIFY   = os.getenv("FORCE_API_CLASSIFY", "0") == "1"

HF_TIMEOUT = int(os.getenv("HF_TIMEOUT", "20"))
HF_RETRIES = int(os.getenv("HF_RETRIES", "3"))
HF_BACKOFF = float(os.getenv("HF_BACKOFF", "1.5"))

CATEGORIES = ["Produtivo", "Improdutivo"]
INTENTS = [
    "STATUS","ATTACHMENT","ACCESS","ERROR","CLOSURE",
    "THANKS","GREETINGS","SUPPORT","NON_MESSAGE","OTHER"
]

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

# -------------------- Helpers --------------------
def _sanitize_label(label: str, allowed: list[str], default: str) -> str:
    if not label:
        return default
    up = (label or "").strip().upper()
    for a in allowed:
        if up == a.upper():
            return a
    aliases = {
        "PRODUCTIVE": "Produtivo",
        "UNPRODUCTIVE": "Improdutivo",
        "ATTACH": "ATTACHMENT",
        "ATTACHMENT/DOCUMENT": "ATTACHMENT",
        "GREETING": "GREETINGS",
        "SUPPORT": "SUPPORT",
        "SUPORTE": "SUPPORT",
        "THANK": "THANKS",
        "NON-MESSAGE": "NON_MESSAGE",
        "NON_MESSAGE": "NON_MESSAGE",
    }
    return aliases.get(up, default)

def _trim_text(text: str, limit: int = 4000) -> str:
    t = (text or "")
    if len(t) <= limit:
        return t
    half = limit // 2
    return t[:half] + "\n...\n" + t[-half:]

def _openai_classify_and_intent(text: str) -> AIClassifyResult:
    import os
    import openai as _openai
    _openai.api_key = OPENAI_API_KEY
    req_timeout = float(os.getenv("OPENAI_TIMEOUT", "10"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    system = (
        "Você é um classificador de emails corporativos. "
        "Classifique o CONTEÚDO como categoria Produtivo ou Improdutivo, e a subintenção em "
        "STATUS|ATTACHMENT|ACCESS|ERROR|CLOSURE|THANKS|GREETINGS|SUPPORT|NON_MESSAGE|OTHER.\n"
        "• NON_MESSAGE quando for majoritariamente um documento não-mensagem (CV, portfólio, contrato etc.).\n"
        "Responda SOMENTE JSON: "
        "{\"category\":\"Produtivo|Improdutivo\",\"intent\":\"...\",\"confidence\":0..1}."
    )

    user = f"""
Regras rápidas:
- Se houver pedido claro (status, erro, acesso etc.), category=Produtivo e intent correspondente.
- Documento genérico (CV/Resume, portfolio, manual, política, anúncio): intent=NON_MESSAGE e category=Improdutivo.
- Exemplos:
  • "Segue currículo..." -> {{"category":"Improdutivo","intent":"NON_MESSAGE","confidence":0.9}}
  • "Erro ao salvar, ver prints" -> {{"category":"Produtivo","intent":"ERROR","confidence":0.9}}
  • "Obrigado, era só isso." -> {{"category":"Improdutivo","intent":"THANKS","confidence":0.9}}

Conteúdo:
{_trim_text(text)}
"""

    try:
        t0 = time.perf_counter()
        resp = _openai.chat.completions.create(
            model=model,
            temperature=0.0,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            timeout=req_timeout  # <- apenas 'timeout'
        )
        ms = int((time.perf_counter() - t0) * 1000)
        print(f"[openai] classify ms={ms}")

        raw = (resp.choices[0].message.content or "").strip()
        try:
            data = json.loads(raw)
        except Exception:
            data = {}

        cat = (data.get("category") or "").strip().title()
        if cat not in CATEGORIES:
            cat = "Improdutivo" if (data.get("intent", "").upper() == "NON_MESSAGE") else "Produtivo"

        intent = (data.get("intent") or "").strip().upper()
        if intent not in INTENTS:
            intent = "OTHER"

        conf = float(data.get("confidence", 0.65))
        return AIClassifyResult(True, cat, intent, conf, {"source": "openai", "openai_raw": data})

    except Exception as e:
        print(f"[openai] ERROR classify: {e}")
        return AIClassifyResult(False, "", "OTHER", 0.0, {"error": str(e)})



# --- OPENAI: gerar resposta ---
def _openai_generate_reply(text: str, category: str, intent: str, lang: str) -> str:
    try:
        import os
        import openai as _openai
        _openai.api_key = OPENAI_API_KEY
        req_timeout = float(os.getenv("OPENAI_GEN_TIMEOUT", "10"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        tone_pt = "Use tom corporativo, objetivo e cordial. Retorne APENAS o corpo do e-mail."
        tone_en = "Use a corporate, concise and polite tone. Return ONLY the email body."
        instructions_pt = {
            "STATUS":"Informe que estamos verificando o status; peça ticket/logs se necessário.",
            "ATTACHMENT":"Confirme recebimento do arquivo e que será avaliado; próximos passos em breve.",
            "ACCESS":"Peça e-mail de login e mensagem de bloqueio; ofereça desbloqueio/reset.",
            "ERROR":"Se mencionar anexos, confirme; senão peça passos, horário e logs/prints.",
            "CLOSURE":"Agradeça e confirme encerramento; à disposição.",
            "THANKS":"Agradeça; sem ação.",
            "GREETINGS":"Agradeça os votos; sem ação.",
            "NON_MESSAGE":"Agradeça o documento; explique que esta caixa é para suporte; sem ação.",
            "OTHER":"Confirme recebimento; retornaremos em breve."
        }
        instructions_en = {
            "STATUS":"We're checking the status; ask for ticket/logs if needed.",
            "ATTACHMENT":"Confirm file receipt; will review and follow up.",
            "ACCESS":"Ask for login e-mail / lockout message; offer unlock/password reset.",
            "ERROR":"If attachments mentioned, acknowledge them; else ask steps, time, logs/screens.",
            "CLOSURE":"Thank and confirm closure; stay available.",
            "THANKS":"Thank you; no action.",
            "GREETINGS":"Thanks for the wishes; no action.",
            "NON_MESSAGE":"Thanks for the document; note this inbox is for support; no action.",
            "OTHER":"Confirm receipt; will analyze and follow up soon."
        }
        sign_pt = "Atenciosamente,\nEquipe de Suporte"
        sign_en = "Best regards,\nSupport Team"

        prompt = (
            f"E-mail original:\n{_trim_text(text)}\n\n"
            f"Categoria: {category}\n"
            f"Subintenção: {intent}\n\n"
            f"Instrução: {(instructions_en if lang=='en' else instructions_pt).get(intent,'OTHER')}\n"
            f"{tone_en if lang=='en' else tone_pt}\n\n"
            f"Assinatura: {(sign_en if lang=='en' else sign_pt)} (anexe ao final)"
        )

        t0 = time.perf_counter()
        resp = _openai.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[{"role": "system", "content": "Você redige respostas de e-mail."},
                      {"role": "user", "content": prompt}],
            timeout=req_timeout  # <- apenas 'timeout'
        )
        ms = int((time.perf_counter() - t0) * 1000)
        print(f"[openai] generate ms={ms}")
        return (resp.choices[0].message.content or "").strip()

    except Exception as e:
        print(f"[openai] ERROR generate: {e}")
        return ""


# -------------------- Hugging Face--------------------
def _hf_post(model: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chamada robusta à Inference API com:
    - retries exponenciais (503 = modelo carregando / 429 = rate limit)
    - options.wait_for_model/use_cache para estabilidade
    - logs de latência/status
    """
    if not HUGGINGFACE_API_KEY:
        raise RuntimeError("HUGGINGFACE_API_KEY ausente")

    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # garante options padrão sem sobrescrever as que vierem no payload
    opts = payload.get("options", {})
    opts.setdefault("wait_for_model", True)
    opts.setdefault("use_cache", True)
    payload["options"] = opts

    last_err: Optional[Exception] = None
    for attempt in range(1, HF_RETRIES + 1):
        try:
            t0 = time.perf_counter()
            r = requests.post(url, headers=headers, json=payload, timeout=HF_TIMEOUT)
            ms = int((time.perf_counter() - t0) * 1000)

            # 503 = model loading | 429 = rate limit → backoff e retry
            if r.status_code in (503, 429):
                print(f"[hf] {r.status_code} (retry) model={model} attempt={attempt}/{HF_RETRIES} ms={ms}")
                time.sleep((HF_BACKOFF ** attempt))
                continue

            # outros não-200
            if r.status_code != 200:
                try:
                    body = r.json()
                except Exception:
                    body = {"text": r.text[:200]}
                raise RuntimeError(f"HF non-200 {r.status_code}: {body}")

            out = r.json()
            # alguns endpoints retornam {"error": "..."} mesmo com 200
            if isinstance(out, dict) and out.get("error"):
                err = out.get("error", "")
                print(f"[hf] 200-with-error: {err}")
                time.sleep((HF_BACKOFF ** attempt))
                last_err = RuntimeError(err)
                continue

            print(f"[hf] ok model={model} ms={ms}")
            return out

        except requests.Timeout:
            last_err = RuntimeError("HF timeout")
            print(f"[hf] timeout model={model} attempt={attempt}/{HF_RETRIES}")
            time.sleep((HF_BACKOFF ** attempt))
        except Exception as e:
            last_err = e
            print(f"[hf] post error model={model} attempt={attempt}/{HF_RETRIES}: {e}")
            time.sleep((HF_BACKOFF ** attempt))

    raise RuntimeError(f"HF POST failed after {HF_RETRIES} attempts: {last_err}")

def _hf_zero_shot(text: str, candidate_labels: list[str]):
    payload = {
        "inputs": _trim_text(text),
        "parameters": {
            "candidate_labels": candidate_labels,
            "multi_label": False,
            "hypothesis_template": "This email is about {}."
        },
        "options": {"wait_for_model": True, "use_cache": True}
    }
    return _hf_post(HF_ZEROSHOT_MODEL, payload)


def _hf_generate(text: str, instruction: str, lang: str) -> str:
    """
    Geração com FLAN-T5 (ou equivalente) via Inference API.
    - Backoff interno
    - Trata formatos de retorno (lista/dict) e respostas vazias
    - Max tokens um pouco maior p/ evitar truncamento
    """
    if not HUGGINGFACE_API_KEY:
        return ""

    t = (text or "")
    if len(t) > 4000:
        t = t[:2000] + "\n...\n" + t[-2000:]

    prompt = (
        f"Write a professional corporate email reply in "
        f"{'English' if lang=='en' else 'Portuguese (Brazil)'}.\n"
        f"Instruction: {instruction}\n"
        f"Original:\n{t}\n\n"
        f"Reply:\n"
    )

    candidates = [
        os.getenv("HF_GENERATION_MODEL", "google/flan-t5-base"),
        "google/flan-t5-base",
        "google/flan-t5-small",
    ]

    params = {
        "max_new_tokens": 220,
        "temperature": 0.2,
        "do_sample": False
    }

    for repo in candidates:
        payload = {
            "inputs": prompt,
            "parameters": params,
            "options": {"wait_for_model": True, "use_cache": True}
        }
        for attempt in range(1, HF_RETRIES + 1):
            try:
                start = time.perf_counter()
                out = _hf_post(repo, payload)
                ms = int((time.perf_counter() - start) * 1000)
                print(f"[hf] gen repo={repo} ms={ms} attempt={attempt}/{HF_RETRIES}")

                # Possíveis formatos:
                # 1) [{"generated_text": "..."}]
                # 2) {"generated_text": "..."}
                # 3) [{"generated_text": "prompt...Reply: ..."}] → cortar após "Reply:"
                text_out = ""
                if isinstance(out, list) and out:
                    cand = out[0] or {}
                    text_out = cand.get("generated_text", "")
                elif isinstance(out, dict):
                    text_out = out.get("generated_text", "")

                if not text_out:
                    # alguns modelos retornam somente o "token stream" — tentar extrair do payload
                    print("[hf] gen empty response, retrying…")
                    time.sleep(HF_BACKOFF * attempt)
                    continue

                # se veio o prompt + "Reply:", corta e mantém só a parte final
                if "Reply:" in text_out:
                    text_out = text_out.split("Reply:", 1)[-1].strip()

                return (text_out or "").strip()

            except Exception as e:
                print(f"[hf] gen error repo={repo} attempt={attempt}/{HF_RETRIES}: {e}")
                time.sleep(HF_BACKOFF * attempt)

    return ""



def _hf_classify_and_intent(text: str) -> AIClassifyResult:
    """
    Dois zero-shots independentes (categoria e subintenção), com normalização de saída.
    """
    try:
        # Categoria: Produtivo | Improdutivo
        cat_res = _hf_zero_shot(text, ["Produtivo", "Improdutivo"])
        # Formato típico: {"sequence":"...", "labels":[...], "scores":[...]}
        if isinstance(cat_res, dict) and cat_res.get("labels"):
            cat = str(cat_res["labels"][0])
            cat_score = float(cat_res["scores"][0])
        elif isinstance(cat_res, list) and cat_res and isinstance(cat_res[0], dict) and cat_res[0].get("labels"):
            cat = str(cat_res[0]["labels"][0])
            cat_score = float(cat_res[0]["scores"][0])
        else:
            cat, cat_score = "Produtivo", 0.6

        # Intenção
        intent_res = _hf_zero_shot(text, INTENTS)
        if isinstance(intent_res, dict) and intent_res.get("labels"):
            raw_intent = str(intent_res["labels"][0])
            intent_score = float(intent_res["scores"][0])
        elif isinstance(intent_res, list) and intent_res and isinstance(intent_res[0], dict) and intent_res[0].get("labels"):
            raw_intent = str(intent_res[0]["labels"][0])
            intent_score = float(intent_res[0]["scores"][0])
        else:
            raw_intent, intent_score = "OTHER", 0.6

        intent = _sanitize_label(raw_intent, INTENTS, "OTHER")
        cat_norm = _sanitize_label(cat, CATEGORIES, "Produtivo")

        conf = (cat_score + intent_score) / 2.0
        return AIClassifyResult(
            True,
            cat_norm,
            intent,
            float(conf),
            {"source": "huggingface", "hf_raw": {"cat": cat_res, "intent": intent_res}},
        )
    except Exception as e:
        print(f"[hf] ERROR classify: {e}")
        return AIClassifyResult(False, "", "OTHER", 0.0, {"error": str(e)})


def _hf_generate_reply(text: str, category: str, intent: str, lang: str) -> str:
    try:
        instructions = {
            "STATUS": "We are checking the status and will get back soon; ask for ticket/logs if needed.",
            "ATTACHMENT": "Confirm file receipt and say it will be reviewed; follow up with next steps.",
            "ACCESS": "Ask for login e-mail and whether there is a lockout message; offer unlock/password reset.",
            "ERROR": "Ask for reproduction steps, approximate time, and any logs/screenshots. If attachments were mentioned, acknowledge them.",
            "CLOSURE": "Thank and confirm closure; keep availability if anything else is needed.",
            "THANKS": "Thank for the message; no action required.",
            "GREETINGS": "Thank for the wishes; no action required.",
            "NON_MESSAGE": "Thank for the document and clarify this inbox is for support requests; no action required.",
            "SUPPORT": "Acknowledge a technical support request and say the team will review and reply with guidance.",
            "OTHER": "Confirm receipt; say you will analyze and follow up soon."
        }
        instr = instructions.get(intent, instructions["OTHER"])
        return _hf_generate(text, instr, lang)
    except Exception as e:
        print(f"[hf] ERROR generate: {e}")
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
    t = _norm(text or "")
    if not t:
      return None
    none_markers = ["curriculo", "currículo", "resume", "curriculum", "portfólio", "portfolio", "linkedin.com/in/", "contrato", "contract", "manual", "política", "policy", "anúncio", "announcement"]
    action_markers = ["status", "ticket", "protocolo", "erro", "error", "acesso", "login", "suporte", "support"]
    if any(m in t for m in none_markers) and not any(m in t for m in action_markers):
        return {"category": "Improdutivo", "intent": "NON_MESSAGE", "confidence": 0.9}

    try:
        cfg = _load_intent_cfg()
    except Exception:
        return None

    hits_by_intent = {}
    for intent, terms in cfg.get("synonyms", {}).items():
        count = sum(1 for term in terms if _norm(term) in t)
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
    if 80 <= len(t) <= 800:
        conf += 0.05
    conf = max(0.55, min(conf, 0.95))

    category = "Produtivo" if intent in {"STATUS", "ATTACHMENT", "ACCESS", "ERROR", "SUPPORT"} else "Improdutivo"
    return {"category": category, "intent": intent, "confidence": float(conf)}

# -------------------- API pública --------------------
def ai_classify(text: str) -> AIClassifyResult:
    """
    Prioriza o provedor (OPENAI/HF); se falhar e FORCE_API_CLASSIFY=0, cai para fastpath local.
    """
    # 1) Tenta provedor configurado
    if PROVIDER == OPENAI and OPENAI_API_KEY:
        try:
            res = _openai_classify_and_intent(text)
            if res.ok:
                return res
        except Exception as e:
            print(f"[openai] ERROR classify: {e}")

    if PROVIDER == HF and HUGGINGFACE_API_KEY:
        try:
            res = _hf_classify_and_intent(text)
            if res.ok:
                return res
        except Exception as e:
            print(f"[hf] ERROR classify: {e}")

    # 2) Se não for para **forçar** API, usa fastpath local
    if not FORCE_API_CLASSIFY:
        hp = fastpath_from_config(text)
        if hp:
            print(f"[fastpath] intent={hp['intent']} conf={hp['confidence']:.3f}")
            return AIClassifyResult(True, hp["category"], hp["intent"], hp["confidence"], {"source": "fastpath"})

    # 3) Caso nada funcione
    return AIClassifyResult(False, "", "OTHER", 0.0, {"error": "provider-not-configured-or-failed"})


def ai_generate_reply(text: str, category: str, intent: str, lang: str) -> str:
    if PROVIDER == OPENAI and OPENAI_API_KEY:
        try:
            return _openai_generate_reply(text, category, intent, lang)
        except Exception as e:
            print(f"[openai] ERROR generate: {e}")
    if PROVIDER == HF and HUGGINGFACE_API_KEY:
        try:
            return _hf_generate_reply(text, category, intent, lang)
        except Exception as e:
            print(f"[hf] ERROR generate: {e}")
    return ""
