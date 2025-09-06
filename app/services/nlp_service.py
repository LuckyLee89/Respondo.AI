import re
import nltk

def ensure_nltk():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)

ensure_nltk()

def detect_language(text: str) -> str:
    """Heurística simples PT/EN com viés pró-PT quando houver empate ou termos técnicos mistos."""
    t = (text or "").lower()

    pt_markers = [
        'por favor','obrigado','obrigada','bom dia','boa tarde','boa noite',
        'anexo','andamento','protocolo','atualização','atualizacao',
        'solicitação','solicitacao','dúvida','duvida','aguardo','retorno',
        'segue em anexo','favor', 'previsão','previsao','chamado','incidente'
    ]
    en_markers = [
        'please','thanks','thank you','hi','hello','attachment','status',
        'ticket','update','request','question','regards','case'
    ]

    # conta ocorrências
    pt_score = sum(t.count(m) for m in pt_markers)
    en_score = sum(t.count(m) for m in en_markers)

    technical = ['gpu','driver','firmware','windows','log','screenshot','error','bug','rtx','intel','nvidia']
    tech_hits = sum(t.count(m) for m in technical)

    if en_score >= pt_score + 2:
        return 'en'
    return 'pt'


def stopwords(lang='pt'):
    from nltk.corpus import stopwords as sw
    return set(sw.words('english' if lang=='en' else 'portuguese'))

def preprocess(text: str, lang: str = 'pt') -> str:
    t = (text or "").lower()
    t = re.sub(r'(?m)^>.*$', ' ', t)                   # contador de linhas
    t = re.sub(r'https?://\S+|www\.\S+', ' ', t)       # urls
    t = re.sub(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', ' ', t)  # emails
    t = re.sub(r'\b\d{6,}\b', ' ', t)                  # lnumeros Longos
    t = re.sub(r'[^\w\s]', ' ', t)                     # pontuação
    t = re.sub(r'\s+', ' ', t)                         # espaços extras
    toks = [w for w in t.split() if w not in stopwords(lang)]
    return ' '.join(toks)
