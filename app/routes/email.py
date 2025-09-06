from flask import Blueprint, render_template, request, jsonify
from ..services.nlp_service import detect_language, preprocess
from ..utils.extract import extract_text_from_pdf, extract_text_from_txt
from ..services.response_service import build_reply
import re

email_bp = Blueprint("email", __name__)

@email_bp.get("/")
def index():
    return render_template("index.html")

def _pick_intent(*candidates):
    """CLOSURE vence sempre; depois voto + precedência."""
    PRIOR = ["CLOSURE","ERROR","STATUS","ATTACHMENT","ACCESS","THANKS","GREETINGS","SUPPORT","OTHER"]
    cands = [c for c in candidates if c]
    if not cands:
        return "OTHER"
    if "CLOSURE" in cands:
        return "CLOSURE"
    counts = {k: cands.count(k) for k in set(cands)}
    return sorted(counts.items(), key=lambda kv: (-kv[1], PRIOR.index(kv[0]) if kv[0] in PRIOR else 99))[0][0]


@email_bp.post("/classify")
def classify():
    try:
        # 1) arquivo > texto
        raw_text = ""
        if "email_file" in request.files and request.files["email_file"].filename:
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

        if not raw_text or not raw_text.strip():
            return jsonify({"ok": False, "error": "Nenhum texto de email fornecido."}), 400
        if len(raw_text.strip()) < 10:
            return jsonify({"ok": False, "error": "Texto muito curto para classificar. Envie mais detalhes."}), 400

        #NLP
        lang = detect_language(raw_text)
        clean = preprocess(raw_text, lang=lang)

        #API (com fastpath interno) OU local
        from ..services.ai_provider import ai_classify, ai_generate_reply, AIClassifyResult, fastpath_from_config
        ai_res: AIClassifyResult = ai_classify(raw_text)

        # intenção local e de config (sempre calculadas)
        from ..services.classifier_service import classifier_service, detect_intent
        intent_local = detect_intent(raw_text, lang)
        fp = fastpath_from_config(raw_text) or {}
        intent_cfg = fp.get("intent")

        if ai_res.ok:
            label_api = ai_res.category                 
            proba = ai_res.confidence or 0.0               
            intent_api = ai_res.intent
            top_feats = []
            label_local = None
        else:
            label_api = None
            label_local, proba, top_feats = classifier_service.predict(clean)
            intent_api = None

        intent = _pick_intent(intent_api, intent_local, intent_cfg)
        ERROR_SIGNS = r"\b(erro|falha|bug|inoperante|indispon[ií]vel|lentid[aã]o|exce[cç][aã]o|problema|incidente|error|failure|crash|timeout|stacktrace|exception|issue|incident)\b"
        if intent == "ATTACHMENT" and re.search(ERROR_SIGNS, (raw_text or "").lower()):
            intent = "ERROR"

        PRODUCTIVE = {"STATUS","ATTACHMENT","ACCESS","ERROR","SUPPORT"}
        forced_label = "Produtivo" if intent in PRODUCTIVE else "Improdutivo"

        source_label = label_api if ai_res.ok else label_local
        source_conf = float(proba or 0.0)

        if source_label and source_label != forced_label:
            source_conf = min(source_conf, 0.75)

        label = forced_label
        proba = source_conf

        debug = {
            "provider": "api" if ai_res.ok else "local",
            "intent_api": intent_api,
            "intent_local": intent_local,
            "intent_cfg": intent_cfg,
            "intent_final": intent,
            "label_api": label_api,
            "label_local": label_local,
            "label_final": label,
            "conf_input": float((ai_res.confidence if ai_res.ok else proba) or 0.0),
            "conf_final": float(proba),
            "forced": bool(source_label and source_label != label)
        }

        #Respostas (API se houver; senão template)
        reply_pt = reply_en = ""
        try:
            if ai_res.ok:
                reply_pt = (ai_generate_reply(raw_text, label, intent, "pt") or "").strip()
                reply_en = (ai_generate_reply(raw_text, label, intent, "en") or "").strip()
        except Exception:
            pass
        if not reply_pt:
            reply_pt = build_reply(raw_text, category=label, lang='pt', intent=intent).strip()
        if not reply_en:
            reply_en = build_reply(raw_text, category=label, lang='en', intent=intent).strip()

        return jsonify({
            "ok": True,
            "category": label,
            "probability": round(float(proba or 0.0), 3),
            "reply_pt": reply_pt,
            "reply_en": reply_en,
            "reply_lang_default": "pt",
            "explanation": {
                "top_features": top_feats,
                "language": lang,
                "intent": intent
            },
            "debug": debug,
            "text_preview": raw_text[:2000]
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
