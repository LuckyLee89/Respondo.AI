from flask import Blueprint, render_template, request, jsonify
from ..services.nlp_service import detect_language, preprocess
from ..utils.extract import extract_text_from_pdf, extract_text_from_txt
from ..services.response_service import build_reply
import re
import os
import time
import uuid

email_bp = Blueprint("email", __name__)

REQUIRE_AI = os.getenv("REQUIRE_AI", "true").lower() == "true"


@email_bp.get("/")
def index():
    return render_template("index.html")


def _pick_intent(*candidates):
    """CLOSURE vence sempre; depois voto + precedência."""
    PRIOR = [
        "CLOSURE", "ERROR", "STATUS", "ATTACHMENT", "ACCESS",
        "SUPPORT", "THANKS", "GREETINGS", "NON_MESSAGE", "OTHER",
    ]
    cands = [c for c in candidates if c]
    if not cands:
        return "OTHER"
    if "CLOSURE" in cands:
        return "CLOSURE"
    counts = {k: cands.count(k) for k in set(cands)}
    return sorted(
        counts.items(),
        key=lambda kv: (-kv[1], PRIOR.index(kv[0]) if kv[0] in PRIOR else 99)
    )[0][0]


@email_bp.post("/classify")
def classify():
    req_id = str(uuid.uuid4())[:8]
    t0 = time.perf_counter()

    def _lang_mismatch(target: str, txt: str) -> bool:
        if not txt:
            return False
        low = (txt or "").lower()
        if target == "en":
            pt_markers = ["olá", "prezado", "prezada", "obrigado", "obrigada", "atenciosamente", "equipe de suporte", "favor"]
            if any(m in low for m in pt_markers):
                return True
        if target == "pt":
            en_markers = ["hi,", "dear", "thank you", "thanks", "best regards", "support team"]
            if any(m in low for m in en_markers):
                return True
        try:
            det = detect_language(txt)
            return det != target
        except Exception:
            return False

    try:
        # ------------------ arquivo > texto ------------------
        raw_text = ""
        had_file = False
        if "email_file" in request.files and request.files["email_file"].filename:
            had_file = True
            f = request.files["email_file"]
            name = f.filename.lower()
            if name.endswith(".pdf"):
                raw_text = extract_text_from_pdf(f.stream)
            elif name.endswith(".txt"):
                raw_text = extract_text_from_txt(f.stream)
            else:
                return jsonify({"ok": False, "error": "Formato de arquivo não suportado. Envie .txt ou .pdf."}), 400
        else:
            raw_text = request.form.get("email_text", "")

        # Caso especial: arquivo enviado mas o PDF é só imagem (sem texto)
        doc_only = False
        if had_file and (not raw_text or not raw_text.strip()):
            doc_only = True
            # placeholder só para seguir o pipeline sem dar 400
            raw_text = "(arquivo anexado sem texto extraível; provável imagem/scan)"

        # Se não tem arquivo e nem texto, aí sim erro
        if not doc_only and (not raw_text or not raw_text.strip()):
            return jsonify({"ok": False, "error": "Nenhum texto de email fornecido."}), 400
        if len(raw_text.strip()) < 10 and not doc_only:
            return jsonify({"ok": False, "error": "Texto muito curto para classificar. Envie mais detalhes."}), 400

        # preferência de idioma vinda do front (pt|en|auto)
        preferred_lang = (request.form.get("preferred_lang") or "").strip().lower()
        if preferred_lang not in ("pt", "en", "auto"):
            preferred_lang = "auto"

        # ------------------ NLP básico ------------------
        lang = detect_language(raw_text)           # 'pt' ou 'en'
        clean = preprocess(raw_text, lang=lang)
        chosen_lang = lang if preferred_lang == "auto" else preferred_lang

        # ------------------ IA (HF/OpenAI/Fastpath) ------------------
        from ..services.ai_provider import ai_classify, ai_generate_reply, AIClassifyResult, fastpath_from_config
        ai_start = time.perf_counter()
        ai_res: AIClassifyResult = ai_classify(raw_text)
        ai_ms = int((time.perf_counter() - ai_start) * 1000)

        # ------------------ Intenções locais/config ------------------
        from ..services.classifier_service import classifier_service, detect_intent
        intent_local = detect_intent(raw_text, lang)
        fp = fastpath_from_config(raw_text) or {}
        intent_cfg = fp.get("intent")

        # ------------------ Escolha da fonte de classificação ------------------
        label_api = None
        label_local = None
        top_feats = []
        intent_api = None
        proba = 0.0

        if ai_res.ok:
            label_api = ai_res.category
            proba = ai_res.confidence or 0.0
            intent_api = ai_res.intent
            ai_source = ai_res.raw.get("source") or "api"
        else:
            ai_source = "unavailable"
            if REQUIRE_AI:
                debug = {
                    "req_id": req_id,
                    "provider_env": os.getenv("PROVIDER", "").lower(),
                    "require_ai": True,
                    "ai_source": "unavailable",
                    "ai_error": ai_res.raw.get("error") if ai_res and ai_res.raw else "unknown",
                    "elapsed_ms_total": int((time.perf_counter() - t0) * 1000),
                    "elapsed_ms_ai": ai_ms,
                }
                print(f"[{req_id}] IA indisponível e REQUIRE_AI=true. Erro={debug['ai_error']}")
                return jsonify({"ok": False, "error": "Falha ao chamar o provedor de IA. Verifique a chave/modelo.", "debug": debug}), 502

            # Fallback local permitido
            label_local, proba, top_feats = classifier_service.predict(clean)
            ai_source = "local_fallback"

        # Se for documento puro (scan), força NON_MESSAGE/Improdutivo
        if doc_only:
            intent = "NON_MESSAGE"
        else:
            intent = _pick_intent(intent_api, intent_local, intent_cfg)

            ERROR_SIGNS = r"\b(erro|falha|bug|inoperante|indispon[ií]vel|lentid[aã]o|exce[cç][aã]o|problema|incidente|error|failure|crash|timeout|stacktrace|exception|issue|incident)\b"
            if intent == "ATTACHMENT" and re.search(ERROR_SIGNS, (raw_text or "").lower()):
                intent = "ERROR"

        PRODUCTIVE = {"STATUS", "ATTACHMENT", "ACCESS", "ERROR", "SUPPORT"}
        forced_label = "Improdutivo" if intent == "NON_MESSAGE" else ("Produtivo" if intent in PRODUCTIVE else "Improdutivo")

        source_label = label_api if ai_res.ok else label_local
        source_conf = float(proba or 0.0)
        if source_label and source_label != forced_label:
            source_conf = min(source_conf, 0.75)

        label = forced_label
        proba = source_conf

        # ------------------ Geração da resposta ------------------
        reply_pt = reply_en = ""
        reply_source = "local_template"
        gen_start = time.perf_counter()
        try:
            if ai_res.ok and not doc_only:
                order = [chosen_lang, "en" if chosen_lang == "pt" else "pt"]
                out = {}
                for L in order:
                    gen = (ai_generate_reply(raw_text, label, intent, L) or "").strip()
                    if gen and _lang_mismatch(L, gen):
                        print(f"[{req_id}] descartando resposta {L} por mismatch de idioma")
                        gen = ""
                    out[L] = gen
                reply_pt = out.get("pt", "")
                reply_en = out.get("en", "")
                if reply_pt or reply_en:
                    reply_source = ai_res.raw.get("source") or "api"
        except Exception as e:
            print(f"[{req_id}] Erro ao gerar resposta via IA: {e}")


        if not reply_pt:
            reply_pt = build_reply(raw_text, category=label, lang='pt', intent=intent).strip()
        if not reply_en:
            reply_en = build_reply(raw_text, category=label, lang='en', intent=intent).strip()
        gen_ms = int((time.perf_counter() - gen_start) * 1000)

        # ------------------ Debug & retorno ------------------
        debug = {
            "req_id": req_id,
            "provider_env": os.getenv("PROVIDER", "").lower(),
            "require_ai": REQUIRE_AI,
            "ai_source": ai_source,
            "reply_source": reply_source,
            "intent_api": intent_api,
            "intent_local": intent_local,
            "intent_cfg": intent_cfg,
            "intent_final": intent,
            "label_api": label_api,
            "label_local": label_local,
            "label_final": label,
            "conf_final": float(proba),
            "elapsed_ms_ai": ai_ms,
            "elapsed_ms_gen": gen_ms,
            "elapsed_ms_total": int((time.perf_counter() - t0) * 1000),
            "doc_only": doc_only,
        }
        print(f"[{req_id}] DEBUG: {debug}")

        return jsonify({
            "ok": True,
            "category": label,
            "probability": round(float(proba or 0.0), 3),
            "reply_pt": reply_pt,
            "reply_en": reply_en,
            "reply_lang_default": (lang if preferred_lang == "auto" else preferred_lang),
            "explanation": {
                "top_features": top_feats,
                "language": lang,
                "intent": intent
            },
            "debug": debug,
            "text_preview": raw_text[:2000]
        })
    except Exception as e:
        print(f"[{req_id}] ERROR: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


