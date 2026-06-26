#!/usr/bin/env python3
"""Gera um hash bcrypt para a variável PAINEL_SENHA_HASH.

Uso:
    python painel/gerar_hash.py <senha>
"""
import sys

import bcrypt


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python painel/gerar_hash.py <senha>", file=sys.stderr)
        return 2
    senha = sys.argv[1].encode()
    hashed = bcrypt.hashpw(senha, bcrypt.gensalt(rounds=12)).decode()
    print(hashed)
    print("\nCole o valor acima na variável PAINEL_SENHA_HASH do arquivo .env", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
