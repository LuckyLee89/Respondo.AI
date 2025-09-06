import re
from datetime import datetime
import unicodedata

SIGN_PT = "Atenciosamente,\nEquipe de Suporte"
SIGN_EN = "Best regards,\nSupport Team"

def _ticket(text: str):
    m = re.search(r'(INC-\d+|\b\d{5,}\b)', text, flags=re.IGNORECASE)
    return m.group(1) if m else None

def _norm(s: str) -> str:
    # normaliza acento e faz lower para bater palavras com e sem acentos
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return (s or "").lower().strip()

def _has_attachment(text: str) -> bool:
    """
    Heurística para detectar anexos / evidências já enviados (PT/EN).
    Evita falsos positivos em frases como "posso enviar logs" ou "vou mandar prints".
    """
    t = _norm(text)

    future_markers = [
        "posso enviar", "vou enviar", "enviarei", "posso mandar", "mandarei",
        "posso encaminhar", "encaminharei", "poderia enviar", "podem me enviar",
        "podem enviar", "podem mandar", "poderiam enviar", "encaminharei",
        "i can send", "i will send", "i’ll send", "will provide", "can provide"
    ]
    if any(m in t for m in future_markers):
        return False

    strong_patterns = [
        # PT
        "em anexo", "segue em anexo", "segue anexo", "conforme anexo",
        "anexei", "anexamos", "anexado", "vai anexo", "vão anexos",
        "comprovante em anexo", "documento em anexo",
        # EN
        "attached", "attachment", "attachments", "please find attached",
        "enclosed", "file attached", "files attached"
    ]
    if any(term in t for term in strong_patterns):
        return True

    generic_terms = [
        "print", "prints", "captura de tela", "screenshot", "screenshots",
        "arquivo", "arquivos", "comprovante", "comprovantes",
        "log", "logs", "evidencia", "evidencias",
        "evidence", "evidences"
    ]
    if any(term in t for term in generic_terms):
        return True

    return False


def build_reply(raw_text: str, category: str, lang: str = 'pt', intent: str | None = None) -> str:
    """
    Gera resposta automática alinhada à subintenção.
    intent: STATUS, ATTACHMENT, ACCESS, ERROR, CLOSURE, THANKS, GREETINGS, OTHER
    """
    t = (raw_text or "").strip()
    ticket = _ticket(t)
    when_pt = datetime.now().strftime('%d/%m/%Y %H:%M')
    when_en = datetime.now().strftime('%Y-%m-%d %H:%M')
    it = (intent or "OTHER").upper()
    has_att = _has_attachment(t)

    # ----------------- EN -----------------
    if (lang or '').lower().startswith('en'):
        sign = f"{SIGN_EN} • {when_en}"

        if category == 'Produtivo':
            if it == "SUPPORT":
                return (
                    f"Hi,\n\n"
                    f"We understand your technical support request. Our team is already reviewing it and will get back to you shortly with further guidance.\n\n"
                    f"{sign}"
                )
            if it == "STATUS":
                return (
                    f"Hi,\n\n"
                    f"Thanks for reaching out. We're checking the current status"
                    f"{f' for ticket {ticket}' if ticket else ''} and will get back to you shortly.\n"
                    f"If possible, please share recent logs/screenshots or the ticket number to speed up the analysis.\n\n"
                    f"{sign}"
                )
            if it == "ATTACHMENT":
                return (
                    f"Hi,\n\n"
                    f"We've received your file"
                    f"{f' related to ticket {ticket}' if ticket else ''}. We'll validate it and reply with next steps.\n\n"
                    f"{sign}"
                )
            if it == "ACCESS":
                return (
                    f"Hi,\n\n"
                    f"Sorry about the access issue. Please confirm your login e-mail and whether you received a lockout message.\n"
                    f"We can proceed with an unlock or password reset as needed.\n\n"
                    f"{sign}"
                )
            if it == "ERROR":
                if has_att:
                    return (
                        f"Hi,\n\n"
                        f"Sorry about the issue"
                        f"{f' on ticket {ticket}' if ticket else ''}. We confirm we've received the attachments and will analyze them along with your report. "
                        f"We'll get back to you shortly with guidance.\n\n"
                        f"{sign}"
                    )
                # sem anexo → peça evidências
                return (
                    f"Hi,\n\n"
                    f"Sorry about the issue"
                    f"{f' on ticket {ticket}' if ticket else ''}. To investigate quickly, please share steps to reproduce, "
                    f"approximate time of occurrence, and any logs/screenshots you may have.\n\n"
                    f"{sign}"
                )

            return (
                f"Hi,\n\n"
                f"Thanks for your message"
                f"{f' regarding ticket {ticket}' if ticket else ''}. We're analyzing it and will share an update soon.\n\n"
                f"{sign}"
            )

        # Improdutivo
        if it == "CLOSURE":
            return f"Hi,\n\nThanks for the update! We'll close the ticket here. If you need anything else, just let us know.\n\n{sign}"
        if it == "THANKS":
            return f"Hi,\n\nYou're welcome! We're here if you need anything else.\n\n{sign}"
        if it == "GREETINGS":
            return f"Hi,\n\nThanks for the message and kind wishes! (No action required.)\n\n{sign}"
        return (
            f"Hi,\n\nThank you for your message. No action is required at this time. "
            f"We're at your disposal if you need anything else.\n\n{sign}"
        )

    # ----------------- PT (padrão) -----------------
    sign = f"{SIGN_PT} • {when_pt}"

    if category == 'Produtivo':
        if it == "SUPPORT":
            return (
                f"Olá,\n\n"
                f"Entendemos a sua solicitação de suporte técnico. Já estamos analisando e retornaremos em breve com orientações.\n\n"
                f"{sign}"
            )
        if it == "STATUS":
            return (
                f"Olá,\n\n"
                f"Obrigado pela mensagem. Estamos verificando o status"
                f"{f' do ticket/protocolo {ticket}' if ticket else ''} e retornaremos em breve com uma atualização.\n"
                f"Se possível, encaminhe logs/prints recentes ou o número do ticket para agilizar a análise.\n\n"
                f"{sign}"
            )
        if it == "ATTACHMENT":
            return (
                f"Olá,\n\n"
                f"Recebemos o arquivo"
                f"{f' referente ao ticket {ticket}' if ticket else ''}. Vamos validar o material e retornaremos com os próximos passos.\n\n"
                f"{sign}"
            )
        if it == "ACCESS":
            return (
                f"Olá,\n\n"
                f"Lamentamos o transtorno com o acesso. Para seguirmos com agilidade, confirme o e-mail de login e se houve mensagem de bloqueio.\n"
                f"Podemos realizar o desbloqueio ou o reset de senha, conforme necessário.\n\n"
                f"{sign}"
            )
        if it == "ERROR":
            if has_att:
                return (
                    f"Olá,\n\n"
                    f"Lamentamos o ocorrido"
                    f"{f' no ticket {ticket}' if ticket else ''}. Confirmamos o recebimento dos anexos e vamos analisá-los em conjunto com o seu relato. "
                    f"Retornaremos em breve com as orientações.\n\n"
                    f"{sign}"
                )
            # sem anexo → peça evidências
            return (
                f"Olá,\n\n"
                f"Lamentamos o ocorrido"
                f"{f' no ticket {ticket}' if ticket else ''}. Para darmos sequência com agilidade, poderia nos enviar os passos para reproduzir, "
                f"o horário aproximado da ocorrência e eventuais logs/prints?\n\n"
                f"{sign}"
            )

        # padrão produtivo
        return (
            f"Olá,\n\n"
            f"Obrigado pelo contato"
            f"{f' sobre o ticket {ticket}' if ticket else ''}. Já estamos analisando sua solicitação e voltamos em breve com uma atualização.\n\n"
            f"{sign}"
        )

    # Improdutivo
    if it == "CLOSURE":
        return f"Olá,\n\nAgradecemos o retorno! Vamos encerrar o chamado por aqui. Caso precise novamente, é só nos acionar.\n\n{sign}"
    if it == "THANKS":
        return f"Olá,\n\nNós que agradecemos! Ficamos à disposição para qualquer outra necessidade.\n\n{sign}"
    if it == "GREETINGS":
        return f"Olá,\n\nObrigado pela mensagem e pelos votos! (Não é necessário retorno.)\n\n{sign}"
    return (
        f"Olá,\n\nObrigado pela mensagem. No momento, não identificamos ações pendentes. "
        f"Permanecemos à disposição para o que precisar.\n\n{sign}"
    )
