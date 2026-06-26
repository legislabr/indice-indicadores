import hmac
import re
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import auth, runner
from .config import DATA_DIR, LEGISLATURA_DEFAULT, CSV_PATTERN, CSV_NAME_RE

BASE_DIR = Path(__file__).resolve().parent
DATA = Path(DATA_DIR)
DATA.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Painel Legisla - Extração de Indicadores")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# --------------------------------------------------------------------------- #
# Autenticação / CSRF
# --------------------------------------------------------------------------- #
async def current_user(request: Request) -> dict | None:
    data = auth.parse_session(request.cookies.get("session"))
    return data


async def require_auth(request: Request) -> dict:
    data = await current_user(request)
    if not data:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return data


def auth_redirect(request: Request):
    """Redirecionamento amigável para /login quando não autenticado."""
    data = auth.parse_session(request.cookies.get("session"))
    if not data:
        return RedirectResponse("/login", status_code=303)
    return data


def _csrf_ok(request: Request, session_data: dict) -> bool:
    token = request.headers.get("X-CSRF-Token", "")
    return bool(token) and hmac.compare_digest(token, session_data.get("csrf", ""))


# --------------------------------------------------------------------------- #
# Utilidades de arquivos
# --------------------------------------------------------------------------- #
def list_csvs() -> list[dict]:
    arquivos = []
    for p in sorted(DATA.glob(CSV_PATTERN), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        arquivos.append(
            {
                "nome": p.name,
                "tamanho": st.st_size,
                "tamanho_kb": round(st.st_size / 1024, 1),
                "modificado": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M"),
            }
        )
    return arquivos


def safe_path(nome: str) -> Path:
    base = DATA.resolve()
    alvo = (DATA / nome).resolve()
    # Evita path traversal: o arquivo precisa estar dentro de DATA
    if base not in alvo.parents:
        raise HTTPException(status_code=404)
    if not re.match(CSV_NAME_RE, alvo.name):
        raise HTTPException(status_code=404)
    if not alvo.is_file():
        raise HTTPException(status_code=404)
    return alvo


# --------------------------------------------------------------------------- #
# Rotas de páginas
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    session = auth_redirect(request)
    if isinstance(session, RedirectResponse):
        return session
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "csrf": session["csrf"],
            "csvs": list_csvs(),
            "status": runner.status(),
            "legislatura": LEGISLATURA_DEFAULT,
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "erro": None})


@app.post("/login")
async def login_post(request: Request, senha: str = Form(...)):
    if not auth.verify_password(senha):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": "Senha inválida."},
            status_code=401,
        )
    token, _ = auth.make_session()
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="strict",
        secure=False,  # HTTPS é garantido pelo Traefik na borda
        max_age=60 * 60 * 12,
        path="/",
    )
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session", path="/")
    return resp


# --------------------------------------------------------------------------- #
# API JSON
# --------------------------------------------------------------------------- #
class RunIn(BaseModel):
    data: str  # ISO YYYY-MM-DD


@app.post("/api/executar")
async def api_executar(payload: RunIn, request: Request):
    session = auth_redirect(request)
    if isinstance(session, RedirectResponse):
        return {"ok": False, "erro": "nao-autenticado"}
    if not _csrf_ok(request, session):
        raise HTTPException(status_code=403, detail="CSRF inválido")

    try:
        dt = datetime.strptime(payload.data, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida (use YYYY-MM-DD).")
    ano_final = dt.year
    mes = f"{dt.month:02d}"

    if runner.is_running():
        raise HTTPException(status_code=409, detail="Já existe uma extração em execução.")

    try:
        await runner.start_run(ano_final=ano_final, mes=mes, legislatura=LEGISLATURA_DEFAULT)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"ok": True, "status": runner.status()}


@app.get("/api/status")
async def api_status(request: Request):
    session = auth_redirect(request)
    if isinstance(session, RedirectResponse):
        return {"ok": False, "erro": "nao-autenticado"}
    return {"ok": True, "status": runner.status(), "csvs": list_csvs()}


@app.post("/api/excluir/{nome:path}")
async def api_excluir(nome: str, request: Request):
    session = auth_redirect(request)
    if isinstance(session, RedirectResponse):
        return {"ok": False, "erro": "nao-autenticado"}
    if not _csrf_ok(request, session):
        raise HTTPException(status_code=403, detail="CSRF inválido")
    if runner.is_running():
        raise HTTPException(status_code=409, detail="Aguarde a extração terminar para excluir arquivos.")
    alvo = safe_path(nome)
    alvo.unlink(missing_ok=True)
    return {"ok": True, "csvs": list_csvs()}


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
@app.get("/download/{nome:path}")
async def download(nome: str, request: Request):
    session = auth_redirect(request)
    if isinstance(session, RedirectResponse):
        return session
    alvo = safe_path(nome)
    return FileResponse(
        path=str(alvo),
        filename=alvo.name,
        media_type="text/csv",
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True}
