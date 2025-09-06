# AutoU — Classificação Inteligente de E‑mails

Aplicação web para **classificar e-mails** e **sugerir respostas automáticas** (PT/EN) usando NLP + IA.

---

## ✨ Principais features

- Upload de `.txt` e `.pdf` ou colagem de texto.
- Classificação **Produtivo** × **Improdutivo** com subintenções (Status, Erro, Acesso, Anexo, Encerramento, Suporte, Agradecimento, Saudação, Geral).
- Resposta sugerida **PT/EN** (templates locais com opção de usar OpenAI/HuggingFace).
- Heurísticas para anexos/evidências e _safety‑latch_ que corrige a categoria a partir da subintenção.
- UI moderna (Tailwind), whitelabel (nome/logo editáveis).

---

## 🧰 Stack

**Backend:** Flask + scikit‑learn • **IA (opcional):** OpenAI / HuggingFace • **Frontend:** HTML + Tailwind • **PDF:** PyMuPDF/PyPDF2

---

## 🚀 Como rodar localmente

> **Importante:** Neste projeto o servidor local é iniciado com `python run.py` (e não `flask run`).  
> Se você quiser usar `flask run`, veja a nota mais abaixo.

1. Clone e entre no projeto

```bash
git clone https://github.com/LuckyLee89/Desafio-AutoU.git
cd Desafio-AutoU
```

2. Crie e ative o ambiente

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

3. Instale

```bash
pip install -r requirements.txt
```

4. Configure variáveis (opcional)  
   Crie seu `.env` a partir do exemplo:

```bash
cp .env.example .env
```

- Para usar o modo local (padrão), deixe `PROVIDER=local`.
- Para usar OpenAI/HuggingFace, preencha as chaves no `.env`.

5. **Inicie o app**

```bash
python run.py
```

Acesse: http://localhost:8080

### OPCIONAL — usando `flask run`

Se quiser iniciar via CLI do Flask, defina as variáveis de app/ambiente e rode:

```bash
# Windows (PowerShell)
$env:FLASK_APP="wsgi.py"; $env:FLASK_ENV="development"; flask run --port 8080

# macOS / Linux (bash/zsh)
export FLASK_APP=wsgi.py FLASK_ENV=development
flask run --port 8080
```

> Em alguns ambientes Windows, o _launcher_ do `flask` pode não estar no PATH do venv — por isso indico `python run.py` como caminho padrão.

---
