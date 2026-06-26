#!/usr/bin/env python3
"""Gera um hash bcrypt (e seu base64) para as variáveis de senha do painel.

Uso:
    python painel/gerar_hash.py <senha>

Imprime duas formas:
  - Hash bcrypt cru  -> PAINEL_SENHA_HASH
  - Hash em base64   -> PAINEL_SENHA_HASH_B64  (recomendado no .env, pois
    evita problemas de "$" na interpolação do docker compose)
"""
import base64
import sys

import bcrypt


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python painel/gerar_hash.py <senha>", file=sys.stderr)
        return 2
    hashed = bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt(rounds=12))
    hashed_str = hashed.decode()
    print("PAINEL_SENHA_HASH=" + hashed_str)
    print("PAINEL_SENHA_HASH_B64=" + base64.b64encode(hashed).decode())
    print("\nCopie o valor de PAINEL_SENHA_HASH_B64 para o .env (recomendado).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
