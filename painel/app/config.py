import base64
import os
from pathlib import Path

# Diretório onde os CSVs e o cache (temp/) são gravados pelo gera_csv.py
DATA_DIR = os.environ.get("DATA_DIR", "./data")

# Caminho do script de extração dentro do container
SCRIPT_PATH = os.environ.get("SCRIPT_PATH", str(Path(__file__).resolve().parent.parent / "scripts" / "gera_csv.py"))

# Legislatura padrão exportada
LEGISLATURA_DEFAULT = int(os.environ.get("LEGISLATURA_ATUAL", "57"))

# Segredo para assinar cookies de sessão (use um valor aleatório forte em produção)
SECRET_KEY = os.environ.get("PAINEL_SECRET_KEY", "defina-um-secret-forte")

# Hash bcrypt da senha do painel.
# Aceita duas formas (preferencial: _B64, pois evita problemas de "$" na
# interpolação do docker compose):
#   - PAINEL_SENHA_HASH_B64: base64 do hash bcrypt (recomendado, sem "$")
#   - PAINEL_SENHA_HASH:     hash bcrypt "cru"
_hash_b64 = os.environ.get("PAINEL_SENHA_HASH_B64", "").strip()
PASSWORD_HASH = (
    base64.b64decode(_hash_b64).decode().strip()
    if _hash_b64
    else os.environ.get("PAINEL_SENHA_HASH", "").strip()
)

# Tempo de vida da sessão (segundos) - padrão 12h
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", str(60 * 60 * 12)))

# Padrão dos arquivos listáveis/baixáveis no painel
CSV_PATTERN = "final_ind_legis_*_ate_*.csv"
CSV_NAME_RE = r"^final_ind_legis_\d+_ate_\d{4}(?:-\d{2})?\.csv$"
