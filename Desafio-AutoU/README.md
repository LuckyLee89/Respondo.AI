# AutoU — Classificação Inteligente de E‑mails

Aplicação web para **classificar e-mails** e **sugerir respostas automáticas** (PT/EN) usando NLP + IA.

---

## ✨ Principais features
- Upload de `.txt` e `.pdf` ou colagem de texto.
- Classificação **Produtivo** × **Improdutivo** com subintenções (Status, Erro, Acesso, Anexo, Encerramento, Suporte, Agradecimento, Saudação, Geral).
- Resposta sugerida **PT/EN** (templates locais com opção de usar OpenAI/HuggingFace).
- Heurísticas para anexos/evidências e *safety‑latch* que corrige a categoria a partir da subintenção.
- UI moderna (Tailwind), whitelabel (nome/logo editáveis).

---

## 🧰 Stack
**Backend:** Flask + scikit‑learn • **IA (opcional):** OpenAI / HuggingFace • **Frontend:** HTML + Tailwind • **PDF:** PyMuPDF/PyPDF2

---

## 🚀 Como rodar localmente

> **Importante:** Neste projeto o servidor local é iniciado com `python run.py` (e não `flask run`).  
> Se você quiser usar `flask run`, veja a nota mais abaixo.

1) Clone e entre no projeto
```bash
git clone https://github.com/LuckyLee89/Desafio-AutoU.git
cd Desafio-AutoU
```

2) Crie e ative o ambiente
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

3) Instale
```bash
pip install -r requirements.txt
```

4) Configure variáveis (opcional)  
Crie seu `.env` a partir do exemplo:
```bash
cp .env.example .env
```
- Para usar o modo local (padrão), deixe `PROVIDER=local`.
- Para usar OpenAI/HuggingFace, preencha as chaves no `.env`.

5) **Inicie o app**
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
> Em alguns ambientes Windows, o *launcher* do `flask` pode não estar no PATH do venv — por isso indicamos `python run.py` como caminho padrão.

---

## ☁️ Deploy (Render / Railway / etc.)

Arquivos já incluídos:
- **Procfile** → `web: gunicorn wsgi:app --workers 2 --threads 8 --timeout 60`
- **runtime.txt** → `python-3.11.9`
- **wsgi.py** → ponto de entrada do Gunicorn

### Render (Web Service)
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:app --workers 2 --threads 8 --timeout 60`
- Env vars: copie as de `.env.example` conforme necessário (PROVIDER, chaves etc.).

---

## 📁 Estrutura
```
app/
 ├─ routes/            # Endpoints Flask
 ├─ services/          # Classifier, IA provider, respostas
 ├─ utils/             # Extração de texto PDF/TXT
 ├─ templates/         # index.html (UI)
 └─ static/            # app.js, style.css, assets
models/                # modelo sklearn (joblib)
intents_config.json    # sinônimos + fastpath
run.py                 # entrada local (python run.py)
wsgi.py                # entrada produção (gunicorn wsgi:app)
Procfile               # start do web service
requirements.txt
runtime.txt
README.md
```

---

## 🧪 Teste rápido
- Upload de um `.txt` com:  
  `Bom dia, poderiam informar o status do chamado 123456?`
- Verifique: subintenção **Status**, categoria **Produtivo**, resposta automática coerente.
- Teste um PDF “genérico” (contrato, etc.) para ver resposta “sem ação necessária”.

---

## 📹 Vídeo (3–5 min)
1. **Introdução** (30s) — objetivo do desafio.  
2. **Demo** (3m) — upload, classificação, resposta sugerida.  
3. **Técnico** (1m) — pipeline NLP, fastpath JSON, IA providers.  
4. **Conclusão** (30s) — aprendizados e próximos passos.

---

## 📜 Licença
Uso acadêmico / demonstração.
