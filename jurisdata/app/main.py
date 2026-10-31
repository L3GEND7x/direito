"""Aplicação web JurisData (FastAPI, páginas renderizadas no servidor)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import config as config_mod
from .connectors import Registro
from .contexto import Contexto, montar
from .rotas_admin import router as router_admin
from .rotas_auth import router as router_auth
from .rotas_operacao import router as router_operacao
from .web import Proibido, Redirecionar, render

logging.basicConfig(level=logging.INFO, format='{"nivel":"%(levelname)s","origem":"%(name)s","msg":"%(message)s"}')

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
)


def criar_app(cfg: config_mod.Config | None = None, registro: Registro | None = None, ctx: Contexto | None = None) -> FastAPI:
    ctx = ctx or montar(cfg or config_mod.carregar(), registro)
    app = FastAPI(title=ctx.cfg.nome_sistema, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.ctx = ctx
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    @app.middleware("http")
    async def cabecalhos(request: Request, call_next):
        resposta = await call_next(request)
        resposta.headers["Content-Security-Policy"] = CSP
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not request.url.path.startswith("/static"):
            resposta.headers["Cache-Control"] = "no-store"
        if ctx.cfg.cookie_secure:
            resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resposta

    @app.exception_handler(Redirecionar)
    async def _redirecionar(request: Request, exc: Redirecionar):
        return RedirectResponse(exc.url, status_code=303)

    @app.exception_handler(Proibido)
    async def _proibido(request: Request, exc: Proibido):
        return render(request, "erro.html", {"titulo": "Acesso não permitido",
                                             "texto": "Seu perfil não permite esta operação, ou o item não existe."},
                      status_code=403)

    @app.get("/saude", include_in_schema=False)
    def saude():
        try:
            with ctx.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception:  # noqa: BLE001
            return JSONResponse({"status": "banco_indisponivel"}, status_code=503)

    app.include_router(router_auth)
    app.include_router(router_operacao)
    app.include_router(router_admin)
    return app


def app_factory() -> FastAPI:  # usado por: uvicorn app.main:app_factory --factory
    return criar_app()
