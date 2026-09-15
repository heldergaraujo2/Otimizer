"""Administrative bootstrap for the first local Otimizer account and license."""

from __future__ import annotations

import getpass
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe

from .accounts import Account, hash_password
from .licensing import Entitlements, License
from .persistence import SQLiteAccountRepository, SQLiteDatabase, SQLiteLicenseRepository


LICENSE_DURATION = timedelta(days=30)
LICENSE_PRICE_CENTS = 0


def _database_path() -> Path:
    configured = os.getenv("OTIMIZER_DB_PATH")
    if configured and configured.strip():
        return Path(configured.strip())
    return Path.home() / ".otimizer" / "otimizer.db"


def main() -> None:
    database = SQLiteDatabase(_database_path())
    accounts = SQLiteAccountRepository(database)
    licenses = SQLiteLicenseRepository(database)

    email = input("E-mail da conta: ").strip()
    if not email:
        raise SystemExit("E-mail não pode ser vazio.")

    if accounts.get_by_email(email) is not None:
        raise SystemExit("Já existe uma conta com esse e-mail.")

    password = getpass.getpass("Senha (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirme a senha: ")

    if password != confirmation:
        raise SystemExit("As senhas não coincidem.")

    password_hash = hash_password(password)

    now = datetime.now(timezone.utc)
    account_id = token_urlsafe(18)
    license_id = token_urlsafe(18)

    account = Account(
        account_id=account_id,
        email=email,
        password_hash=password_hash,
    )

    license_record = License(
        license_id=license_id,
        account_id=account_id,
        starts_at=now,
        expires_at=now + LICENSE_DURATION,
        entitlements=Entitlements(
            route_optimization=True,
            max_devices=1,
            max_routes_per_day=None,
        ),
        price_cents=LICENSE_PRICE_CENTS,
    )

    accounts.save(account)
    licenses.save(license_record)

    print()
    print("Bootstrap concluído com sucesso.")
    print(f"Conta: {account.email}")
    print(f"Account ID: {account.account_id}")
    print(f"License ID: {license_record.license_id}")
    print(f"Licença válida até: {license_record.expires_at.isoformat()}")
    print("Preço da licença: R$ 0,00")
    print("Roteirização: habilitada")


if __name__ == "__main__":
    main()
