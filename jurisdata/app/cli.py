"""Comandos administrativos.

    python -m app.cli criar-admin --nome "Fulana" --email adm@escritorio.adv.br
    python -m app.cli expurgar            # retenção (agendar diariamente)
    python -m app.cli verificar-auditoria # integridade da trilha
    python -m app.cli gerar-chaves        # valores para JURISDATA_SECRET_KEY e JURISDATA_DATA_KEY
"""

from __future__ import annotations

import argparse
import secrets
import sys

from cryptography.fernet import Fernet
from sqlalchemy import select

from . import audit
from .config import carregar
from .contexto import montar
from .models import Perfil, Usuario
from .security import gerar_senha_temporaria, hash_senha
from .services.consultas import expurgar_vencidas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jurisdata")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("criar-admin")
    a.add_argument("--nome", required=True)
    a.add_argument("--email", required=True)
    sub.add_parser("expurgar")
    sub.add_parser("verificar-auditoria")
    sub.add_parser("gerar-chaves")
    args = p.parse_args(argv)

    if args.cmd == "gerar-chaves":
        print(f"JURISDATA_SECRET_KEY={secrets.token_urlsafe(48)}")
        print(f"JURISDATA_DATA_KEY={Fernet.generate_key().decode()}")
        print("Guarde a DATA_KEY em cofre: sem ela os dados criptografados não podem ser lidos.", file=sys.stderr)
        return 0

    ctx = montar(carregar())
    with ctx.fabrica() as db:
        if args.cmd == "criar-admin":
            email = args.email.strip().lower()
            if db.scalar(select(Usuario.id).where(Usuario.email == email)):
                print("Já existe usuário com este e-mail.", file=sys.stderr)
                return 1
            senha = gerar_senha_temporaria()
            u = Usuario(nome=args.nome.strip(), email=email, perfil=Perfil.ADMIN, senha_hash=hash_senha(senha),
                        trocar_senha=True)
            db.add(u)
            db.flush()
            audit.registrar(db, "usuario_criado", None, "usuario", u.id, {"perfil": "admin", "origem": "cli"},
                            email="cli")
            db.commit()
            print(f"Administrador criado: {email}")
            print(f"Senha temporária (troca obrigatória no primeiro acesso): {senha}")
        elif args.cmd == "expurgar":
            print(f"Consultas expurgadas: {expurgar_vencidas(db)}")
        elif args.cmd == "verificar-auditoria":
            integra, falha_id, total = audit.verificar_cadeia(db)
            print(f"Registros verificados: {total}")
            if not integra:
                print(f"CADEIA ROMPIDA no registro {falha_id}", file=sys.stderr)
                return 2
            print("Cadeia íntegra.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
