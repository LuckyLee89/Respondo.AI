import os
import re
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_PATH = os.getenv("MODEL_PATH", "models/model.joblib")

SEED = [
    ("Bom dia, podem informar o status do chamado 123456? Atualização do protocolo.", "Produtivo"),
    ("Segue em anexo o comprovante solicitado. Precisam de mais alguma informação?", "Produtivo"),
    ("Erro ao acessar o sistema desde ontem. Podem ajudar?", "Produtivo"),
    ("Solicito reabertura do ticket 555666. O problema persiste.", "Produtivo"),
    ("Atualizem o andamento do caso em aberto, por favor.", "Produtivo"),
    ("Como alterar minha senha? Não recebi o email de recuperação.", "Produtivo"),
    ("Preciso suporte técnico para integrar o arquivo XML no portal.", "Produtivo"),
    ("Favor confirmar recebimento do documento anexado e prazo.", "Produtivo"),
    ("Previsão para resolução do incidente INC-9001?", "Produtivo"),
    ("Feliz Natal a todos! Muito sucesso!", "Improdutivo"),
    ("Agradeço a ajuda, podem desconsiderar o último email.", "Improdutivo"),
    ("Bom final de semana! Abraços.", "Improdutivo"),
    ("Parabéns pelo excelente trabalho!", "Improdutivo"),
    ("Obrigado, era só isso mesmo.", "Improdutivo"),
    ("Que Deus abençoe a todos!", "Improdutivo"),
    ("Could you please update the status of my ticket 123456?", "Produtivo"),
    ("Attached is the requested invoice. Please confirm receipt.", "Produtivo"),
    ("Happy holidays team! All the best!", "Improdutivo"),
    ("Thank you for the support, you can ignore the last message.", "Improdutivo"),
    ("Podem encerrar o chamado 778899, o problema foi resolvido.", "Improdutivo"),
    ("Pode fechar o ticket 12345, já está ok.", "Improdutivo"),
    ("Pode encerrar o ticket 43210, já foi resolvido.", "Improdutivo"),
    ("Favor fechar o protocolo 987654; está finalizado.", "Improdutivo"),
    ("Solicito encerramento do protocolo 555666. Tudo resolvido.", "Improdutivo")
]

# ------------------------- INTENTS (regex) -------------------------
STATUS_TERMS_PT = r"(status|andamento|previs[aã]o|prazo|atualiza[cç][aã]o|retorno|posi[cç][aã]o|acompanhamento|protocolo|ticket|caso)"
STATUS_TERMS_EN = r"(status|update|eta|progress|follow[- ]?up|ticket|case)"

ATTACH_PT = r"(anexo(s)?|em anexo|segue(m)? (o|a|em) anexo|segue(m)? (arquivo|documento|comprovante)|comprovante|documento|arquivo|prints?)"
ATTACH_EN = r"(attached|attachment|enclosed|please find attached|document|screenshot|screenshots|logs?)"

ACCESS_PT = r"(acesso|logar|login|senha|reset|bloquead[oa]|desbloque|autentica[cç][aã]o|2fa|mfa)"
ACCESS_EN = r"(access|login|signin|password|reset|locked|unlock|authentication|2fa|mfa)"

ERROR_PT = r"(erro|falha|bug|trava|travando|inoperante|indispon[ií]vel|artefatos?|lentid[aã]o|exce[cç][aã]o|problema|incidente)"
ERROR_EN = r"(error|bug|failure|crash|frozen|hang|unavailable|timeout|stacktrace|exception|issue|problem|incident)"

THANKS_PT = r"(obrigad[oa]|valeu|agrade[cç]o|agradeco)"
THANKS_EN = r"(thanks|thank you|thx)"

GREET_PT = r"(feliz|boas festas|parab[eé]ns|sauda[cç][oõ]es|bom dia|boa tarde|boa noite)"
GREET_EN = r"(merry|happy (holidays|christmas|new year)|congratulations|congrats|greetings)"

CLOSURE_PT = r"(pode(m)? (encerrar|fechar)|encerrar (o )?(chamado|ticket|protocolo)|fechar (o )?(chamado|ticket|protocolo)|finalizar (o )?(chamado|ticket|protocolo)|encerramento|desconsiderar|problema (ja )?resolvido)"
CLOSURE_EN = r"((please|kindly)\s*)?(close|closed|resolved|issue\s*closed)(\s*(the )?(ticket|case|issue))?"

import re, unicodedata

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return (s or "").lower()

def detect_intent(text: str, lang: str) -> str:
    """
    Intenções: STATUS, ATTACHMENT, ACCESS, ERROR, CLOSURE, THANKS, GREETINGS, SUPPORT, OTHER
    Prioridade: CLOSURE > ERROR > STATUS > ATTACHMENT > ACCESS > THANKS > GREETINGS > SUPPORT > pedido genérico > OTHER
    """
    t = _norm(text)

    re_closure = re.compile(
        r"(?:\b(encerrar|encerramento|fechar|finalizar|desconsiderar)\b.*\b(chamado|ticket|protocolo)\b)"
        r"|(?:\bresolvid\w*\b|issue\s*closed|resolved)"
    )
    re_status  = re.compile(r"\b(status|andamento|previsao|prazo|atualizacao|retorno|posicao|acompanhamento|ticket|case|protocolo)\b")
    re_access  = re.compile(r"\b(acesso|logar|login|senha|reset|bloquead|desbloque|autenticacao|2fa|mfa|access|signin|password|locked|unlock|authentication)\b")
    re_error   = re.compile(r"\b(erro|falha|bug|trava|travando|inoperante|indisponivel|artefatos?|lentidao|excecao|problema|incidente|error|failure|crash|frozen|hang|timeout|stacktrace|exception|issue|incident)\b")
    re_thanks  = re.compile(r"\b(obrigado|obrigada|valeu|agradeco|agradeço|thanks|thank you|thx)\b")
    re_greet   = re.compile(r"\b(bom dia|boa tarde|boa noite|boas festas|feliz natal|feliz ano|saudacoes|sauda[cç]oes|merry|happy (holidays|christmas|new year)|congratulations|congrats|greetings)\b")
    re_support = re.compile(
        r"\b(suporte(?:\s+tecnic[oa])?|technical support|support)\b.*\b(ajuda|ajudar|preciso|poderia|pode(?:m)?|gostaria|solicito|"
        r"integrar|instalar|configurar|setup|integra[cç][aã]o|instala[cç][aã]o|configura[cç][aã]o|help|assist)\b"
    )
    
    re_attach = re.compile(
      r"\b("
      r"em\s+anexo|"
      r"segue(?:m)?\s+(?:em\s+)?anexo[s]?|"
      r"conforme\s+anexo|"
      r"anexei|anexamos|anexado[s]?|"
      r"vai\s+anexo|vão\s+anexos|"
      r"attached|attachment[s]?|enclosed|"
      r"please\s+find\s+attached"
      r")\b"
    )
    if re_attach.search(t):  return "ATTACHMENT"
    if re_closure.search(t): return "CLOSURE"
    if re_error.search(t):   return "ERROR"
    if re_status.search(t):  return "STATUS"

    if re.search(r"\b(anex\w+|em\s+anexo|segue(?:m)?\s+em\s+anexo|attached|attachment|enclosed|please\s+find\s+attached|logs?|screenshots?)\b", t):
        return "ATTACHMENT"

    if re_access.search(t):  return "ACCESS"

    if re_thanks.search(t): return "THANKS"
    if re_greet.search(t):  return "GREETINGS"

    if re_support.search(t): return "SUPPORT"

    if re.search(r"\b(pode(m)?|podem|poderia(m)?|preciso|consegue(m)?)\b", t):
        return "STATUS"

    return "OTHER"

# ------------------------- CLASSIFIER -------------------------
class _ClassifierService:
    def __init__(self):
        self.pipeline = None
        self._ensure_model()

    def _ensure_model(self):
        if os.path.exists(MODEL_PATH):
            self.pipeline = joblib.load(MODEL_PATH)
        else:
            self._train_and_save()

    def _train_and_save(self):
        texts, labels = zip(*SEED)
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))
        ])

        self.pipeline.fit(texts, labels)
        os.makedirs(os.path.dirname(MODEL_PATH) or ".", exist_ok=True)
        joblib.dump(self.pipeline, MODEL_PATH)

    def predict(self, clean_text):
        probs = self.pipeline.predict_proba([clean_text])[0]
        classes = self.pipeline.classes_
        idx = probs.argmax()
        label = classes[idx]
        proba = float(probs[idx])

        top = []
        try:
            clf = self.pipeline.named_steps['clf']
            vec = self.pipeline.named_steps['tfidf']
            feature_names = vec.get_feature_names_out()
            X = vec.transform([clean_text])
            nnz = X.nonzero()[1]

            if clf.coef_.shape[0] > idx:
                scored = sorted(
                    [(feature_names[i], clf.coef_[idx][i]) for i in nnz],
                    key=lambda x: x[1],
                    reverse=True
                )
                top = [t for t, c in scored[:6] if c > 0]
        except Exception:
            top = []

        return label, proba, top

classifier_service = _ClassifierService()
