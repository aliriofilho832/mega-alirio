
# Mega Alirio — Streamlit

Aplicação Streamlit com senha via variável de ambiente `APP_PASSWORD`.

## Como rodar localmente

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# Defina a senha
# Windows (PowerShell)
$env:APP_PASSWORD="minha_senha_local"
# macOS/Linux
export APP_PASSWORD="minha_senha_local"

streamlit run app.py
```

## Deploy no Render
- Configure a variável de ambiente **APP_PASSWORD**.
- Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- Após o build, acesse a URL pública.
