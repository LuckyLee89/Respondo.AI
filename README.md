# AutoU — Classificação Inteligente de E-mails

Aplicação web para **classificar e-mails** e **sugerir respostas automáticas** (PT/EN) usando NLP + IA.  
Agora com **tela de login** protegida por senha e suporte a logout.

---

## ✨ Principais features

- Tela inicial de **login** (com armazenamento local de sessão).
- Campo de senha com **mostrar/ocultar** (olhinho).
- Botão de **logout** para encerrar sessão.
- Upload de `.txt` e `.pdf` ou colagem de texto.
- Classificação **Produtivo** × **Improdutivo** com subintenções (Status, Erro, Acesso, Anexo, Encerramento, Suporte, Agradecimento, Saudação, Documento, Geral).
- Resposta sugerida **PT/EN** (templates locais + geração por OpenAI ou HuggingFace).
- Heurísticas para anexos/evidências e _safety-latch_ que corrige a categoria a partir da subintenção.
- UI moderna (Tailwind), whitelabel (nome/logo editáveis).
- Deploy pronto para Render (Gunicorn + Flask).

---

## 🧰 Stack

**Backend:** Flask + scikit-learn  
**IA (pluggable):** OpenAI / HuggingFace / Fastpath local  
**Frontend:** HTML + Tailwind  
**PDF:** PyMuPDF / PyPDF2

---

## 🚀 Como rodar localmente

> **Importante:** O servidor local é iniciado com `python run.py` (e não `flask run`).  
> Se você quiser usar `flask run`, veja a nota mais abaixo.

1. Clone e entre no projeto:

```bash
git clone https://github.com/LuckyLee89/Desafio-AutoU.git
cd Desafio-AutoU
```

2. Crie e ative o ambiente:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

3. Instale dependências:

```bash
pip install -r requirements.txt
```

4. Configure variáveis de ambiente:  
   Crie seu `.env` a partir do exemplo:

```bash
cp .env.example .env
```

- Para usar **modo local (fastpath)**, deixe `PROVIDER=local`.
- Para usar **OpenAI**, defina `PROVIDER=openai` e preencha `OPENAI_API_KEY`.
- Para usar **HuggingFace**, defina `PROVIDER=huggingface` e preencha `HUGGINGFACE_API_KEY`.
- Para ativar login por senha, defina:
  ```ini
  LOGIN_PASSWORD=suasenha
  ```

5. **Inicie o app**:

```bash
python run.py
```

Acesse: [http://localhost:8080](http://localhost:8080)

---

### 🔄 Alternativa: `flask run`

Se preferir iniciar via CLI do Flask, defina as variáveis e rode:

```bash
# Windows (PowerShell)
$env:FLASK_APP="wsgi.py"; $env:FLASK_ENV="development"; flask run --port 8080

# macOS / Linux (bash/zsh)
export FLASK_APP=wsgi.py FLASK_ENV=development
flask run --port 8080
```

> Em alguns ambientes Windows, o comando `flask` pode não estar no PATH do venv — por isso indicamos `python run.py` como caminho padrão.

---

## 🌐 Deploy no Render

1. Crie `Procfile` na raiz:

   ```
   web: gunicorn "app:create_app()" --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
   ```

2. (Opcional) defina `runtime.txt`:

   ```
   python-3.10.14
   ```

3. Faça push para o GitHub e crie um **Web Service** no [Render](https://render.com/):

   - Build Command: `pip install -r requirements.txt`
   - Start Command: mesmo do Procfile
   - Health Check Path: `/health`

4. Defina variáveis de ambiente no Render:

   - `PROVIDER=openai`
   - `OPENAI_API_KEY=...`
   - `OPENAI_MODEL=gpt-4o-mini`
   - `OPENAI_TIMEOUT=8`
   - `OPENAI_GEN_TIMEOUT=10`
   - `REQUIRE_AI=true`
   - `FORCE_API_CLASSIFY=0`
   - `LOGIN_PASSWORD=suasenha`

5. Acesse a URL gerada (ex.: `https://autou.onrender.com`).

---

## 📂 Estrutura do Projeto

```
app/
 ├── __init__.py        # create_app
 ├── routes/            # rotas Flask (email, config, health, login)
 ├── services/          # ai_provider, classifier, nlp, response
 ├── utils/             # extract (PDF/txt)
 ├── templates/         # index.html, login.html
 └── static/            # app.js, style.css
intents_config.json     # sinônimos/heurísticas
requirements.txt
Procfile
run.py
wsgi.py
```

---

## 🔑 Login

- A primeira página é o **login**.
- A senha é validada com `LOGIN_PASSWORD` definida no `.env`.
- O login é armazenado no **localStorage** → se atualizar a página, continua logado.
- Botão de **logout** para encerrar a sessão.
- Campo de senha com **mostrar/ocultar (olhinho)** integrado.
