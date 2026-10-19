#!/usr/bin/env python3
import sys
from afd import carregar, tabela, descrever_finais

with open(sys.argv[1], encoding="utf-8") as f:
    afnd = carregar(f.read())

print("=== AFND (carga) ===\n")
print(f"Determinístico: {'sim' if afnd.deterministico() else 'não'}\n")
print(tabela(afnd))
print("\nEstados finais:")
print(descrever_finais(afnd))