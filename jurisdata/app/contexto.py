from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .config import Config
from .connectors import Registro
from .db import Base, criar_engine, criar_fabrica
from .security import Cofre


@dataclass
class Contexto:
    cfg: Config
    engine: Engine
    fabrica: sessionmaker
    cofre: Cofre
    registro: Registro


def montar(cfg: Config, registro: Registro | None = None, criar_tabelas: bool = True) -> Contexto:
    cfg.validar()
    engine = criar_engine(cfg.database_url)
    if criar_tabelas:
        from . import models  # noqa: F401 - registra as tabelas

        Base.metadata.create_all(engine)
    return Contexto(
        cfg=cfg,
        engine=engine,
        fabrica=criar_fabrica(engine),
        cofre=Cofre(cfg.data_key, cfg.secret_key),
        registro=registro or Registro(cfg),
    )
