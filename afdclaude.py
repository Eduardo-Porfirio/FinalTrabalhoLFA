#!/usr/bin/env python3
"""
Gerador de AFD a partir de tokens e Gramáticas Regulares (GR) em BNF.

Etapas (conforme o enunciado do projeto de LFA):
  1. Carga: lê tokens e GRs de um arquivo texto e monta um único AFND.
     Apenas o estado inicial é compartilhado; toda nova transição cria
     um novo estado destino.
  2. Determinização: construção de subconjuntos (teorema da determinização).
  3. Minimização sem classes de equivalência: remoção de estados
     inalcançáveis e de estados mortos.
  4. Estado de erro: acrescenta um último estado (final) de erro e
     preenche com ele todas as células não mapeadas.

Uso:
  python3 afd.py exemplos/enunciado.txt
  python3 afd.py exemplos/enunciado.txt --saida resultado.md
  python3 afd.py exemplos/enunciado.txt --testar "se senao aeiou xyz"
"""

import argparse
import re
import sys

EPSILON = ""                          # rótulo interno das transições ε
SIMBOLOS_EPSILON = {"ε", "&", "eps"}  # formas aceitas no arquivo de entrada
ESTADO_INICIAL = "S"
ESTADO_ERRO = "ERR"
ROTULO_ERRO = "erro"

REGRA_GR = re.compile(r"^<([^<>]+)>\s*::=\s*(.*)$")
PRODUCAO = re.compile(r"^(.*?)(?:<([^<>]+)>)?$")


class AF:
    """Autômato finito (determinístico ou não).

    transicoes[estado][simbolo] = conjunto de estados destino.
    finais[estado] = lista de rótulos (token ou GR) reconhecidos ali.
    """

    def __init__(self):
        self.estados = []
        self.inicial = None
        self.finais = {}
        self.transicoes = {}
        self.alfabeto = []
        self.prioridade = {}  # rótulo -> ordem de preferência

    def add_estado(self, nome):
        if nome not in self.transicoes:
            self.estados.append(nome)
            self.transicoes[nome] = {}
        return nome

    def add_transicao(self, origem, simbolo, destino):
        if simbolo != EPSILON and simbolo not in self.alfabeto:
            self.alfabeto.append(simbolo)
        self.transicoes[origem].setdefault(simbolo, set()).add(destino)

    def add_final(self, estado, rotulo):
        rotulos = self.finais.setdefault(estado, [])
        if rotulo not in rotulos:
            rotulos.append(rotulo)

    def rotulo(self, estado):
        """Rótulo de maior prioridade de um estado final."""
        rotulos = self.finais.get(estado)
        if not rotulos:
            return None
        return min(rotulos, key=lambda r: self.prioridade.get(r, len(self.prioridade)))

    def deterministico(self):
        return all(
            simbolo != EPSILON and len(destinos) == 1
            for mapa in self.transicoes.values()
            for simbolo, destinos in mapa.items()
        )

    def copia_vazia(self):
        novo = AF()
        novo.alfabeto = list(self.alfabeto)
        novo.prioridade = dict(self.prioridade)
        return novo


# ---------------------------------------------------------------------------
# 1. Carga
# ---------------------------------------------------------------------------

def gerador_nomes(reservados):
    """A, B, ..., Z, AA, AB, ... pulando nomes reservados (S, ERR)."""
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    tamanho = 1
    while True:
        indices = [0] * tamanho
        while True:
            nome = "".join(letras[i] for i in indices)
            if nome not in reservados:
                yield nome
            pos = tamanho - 1
            while pos >= 0 and indices[pos] == len(letras) - 1:
                indices[pos] = 0
                pos -= 1
            if pos < 0:
                break
            indices[pos] += 1
        tamanho += 1


class Carregador:
    def __init__(self):
        self.af = AF()
        self.af.inicial = self.af.add_estado(ESTADO_INICIAL)
        self.nomes = gerador_nomes({ESTADO_INICIAL, ESTADO_ERRO})
        self.num_gr = 0
        self.rotulos_tokens = []
        self.rotulos_gr = []

    def novo_estado(self):
        return self.af.add_estado(next(self.nomes))

    def carregar_token(self, token):
        atual = self.af.inicial
        for simbolo in token:
            destino = self.novo_estado()
            self.af.add_transicao(atual, simbolo, destino)
            atual = destino
        self.af.add_final(atual, token)
        if token not in self.rotulos_tokens:
            self.rotulos_tokens.append(token)

    def carregar_gramatica(self, regras, rotulo=None):
        """regras: lista de (não-terminal, texto das alternativas)."""
        self.num_gr += 1
        rotulo = rotulo or f"GR{self.num_gr}"
        self.rotulos_gr.append(rotulo)

        simbolo_inicial = regras[0][0]
        producoes = [(nt, self._separar(alts)) for nt, alts in regras]

        # O símbolo inicial da GR é o estado inicial do AF. Se ele aparece
        # no lado direito de alguma produção, ganha um estado próprio
        # (senão o retorno ao inicial misturaria a GR com os outros tokens);
        # nesse caso o estado inicial recebe uma cópia das suas transições.
        recursivo = any(nt_dest == simbolo_inicial
                        for _, alts in producoes for _, nt_dest in alts)
        estado_de = {}
        if not recursivo:
            estado_de[simbolo_inicial] = self.af.inicial

        def estado(nt):
            if nt not in estado_de:
                estado_de[nt] = self.novo_estado()
            return estado_de[nt]

        for nt, alternativas in producoes:
            origem = estado(nt)
            for terminais, nt_dest in alternativas:
                if not terminais and nt_dest is None:      # A ::= ε
                    self.af.add_final(origem, rotulo)
                    continue
                if not terminais:                          # A ::= <B>
                    self.af.add_transicao(origem, EPSILON, estado(nt_dest))
                    continue
                atual = origem
                for i, simbolo in enumerate(terminais):
                    ultimo = i == len(terminais) - 1
                    if ultimo and nt_dest is not None:
                        destino = estado(nt_dest)
                    else:
                        destino = self.novo_estado()
                    self.af.add_transicao(atual, simbolo, destino)
                    atual = destino
                if nt_dest is None:                        # A ::= a
                    self.af.add_final(atual, rotulo)

        if recursivo:
            proprio = estado_de[simbolo_inicial]
            for simbolo, destinos in self.af.transicoes[proprio].items():
                for destino in destinos:
                    self.af.add_transicao(self.af.inicial, simbolo, destino)
            if proprio in self.af.finais:
                self.af.add_final(self.af.inicial, rotulo)

    @staticmethod
    def _separar(texto):
        """'a<A> | b | ε' -> [('a', 'A'), ('b', None), ('', None)]"""
        alternativas = []
        for alt in texto.split("|"):
            alt = alt.strip()
            if alt in SIMBOLOS_EPSILON:
                alt = ""
            terminais, nt = PRODUCAO.match(alt).groups()
            terminais = "".join(terminais.split())  # ignora espaços
            if "<" in terminais or ">" in terminais:
                raise ValueError(f"produção inválida: '{alt}' (o não-terminal deve ficar no fim)")
            alternativas.append((terminais, nt))
        return alternativas

    def finalizar(self):
        # Palavras reservadas/tokens têm prioridade sobre as GRs (ex.: "se"
        # reconhecido como palavra reservada e não como identificador).
        ordem = self.rotulos_tokens + self.rotulos_gr
        self.af.prioridade = {r: i for i, r in enumerate(ordem)}
        return self.af


def carregar(texto):
    """Lê o conteúdo do arquivo de entrada e devolve o AFND.

    - Cada linha que não é regra BNF é um token (sequência de símbolos).
    - Linhas consecutivas no formato <X> ::= ... formam uma GR; a primeira
      regra define o símbolo inicial. Linha em branco ou token encerram a GR.
    - Uma linha '#gr nome' antes de uma GR dá nome a ela (opcional).
    """
    carregador = Carregador()
    bloco, nome_bloco, proximo_nome = [], None, None

    def fechar_bloco():
        nonlocal bloco, nome_bloco
        if bloco:
            carregador.carregar_gramatica(bloco, nome_bloco)
        bloco, nome_bloco = [], None

    for num, linha in enumerate(texto.splitlines(), 1):
        linha = linha.strip()
        if not linha:
            fechar_bloco()
            continue
        if linha.lower().startswith("#gr "):
            fechar_bloco()
            proximo_nome = linha[4:].strip()
            continue
        regra = REGRA_GR.match(linha)
        if regra:
            if not bloco:
                nome_bloco, proximo_nome = proximo_nome, None
            bloco.append((regra.group(1).strip(), regra.group(2)))
            continue
        fechar_bloco()
        carregador.carregar_token(linha)
    fechar_bloco()
    return carregador.finalizar()


# ---------------------------------------------------------------------------
# 2. Determinização
# ---------------------------------------------------------------------------

def fecho_epsilon(af, estados):
    pilha, fecho = list(estados), set(estados)
    while pilha:
        for destino in af.transicoes[pilha.pop()].get(EPSILON, ()):
            if destino not in fecho:
                fecho.add(destino)
                pilha.append(destino)
    return frozenset(fecho)


def nome_conjunto(conjunto, af):
    ordem = {e: i for i, e in enumerate(af.estados)}
    membros = sorted(conjunto, key=ordem.get)
    return membros[0] if len(membros) == 1 else "[" + ",".join(membros) + "]"


def determinizar(afnd, completo=True):
    """Construção de subconjuntos (teorema da determinização).

    Com completo=True, todos os estados do AFND são mantidos na tabela e os
    novos estados compostos ([A,H], ...) são acrescentados ao final, como na
    aplicação do teorema em tabela; os que ficarem inalcançáveis são
    eliminados na minimização. Com completo=False só os estados alcançáveis
    a partir do inicial são gerados."""
    afd = afnd.copia_vazia()
    inicial = fecho_epsilon(afnd, {afnd.inicial})
    nomes = {inicial: nome_conjunto(inicial, afnd)}
    afd.inicial = afd.add_estado(nomes[inicial])
    fila = [inicial]
    if completo:
        for estado in afnd.estados:
            conjunto = fecho_epsilon(afnd, {estado})
            if conjunto not in nomes:
                nomes[conjunto] = nome_conjunto(conjunto, afnd)
                afd.add_estado(nomes[conjunto])
                fila.append(conjunto)
    while fila:
        conjunto = fila.pop(0)
        origem = nomes[conjunto]
        for estado in sorted(conjunto, key=afnd.estados.index):
            for rotulo in afnd.finais.get(estado, []):
                afd.add_final(origem, rotulo)
        for simbolo in afnd.alfabeto:
            alvo = set()
            for estado in conjunto:
                alvo |= afnd.transicoes[estado].get(simbolo, set())
            if not alvo:
                continue
            alvo = fecho_epsilon(afnd, alvo)
            if alvo not in nomes:
                nomes[alvo] = nome_conjunto(alvo, afnd)
                afd.add_estado(nomes[alvo])
                fila.append(alvo)
            afd.add_transicao(origem, simbolo, nomes[alvo])
    return afd


# ---------------------------------------------------------------------------
# 3. Minimização (sem classes de equivalência)
# ---------------------------------------------------------------------------

def restringir(af, manter):
    novo = af.copia_vazia()
    novo.inicial = af.inicial
    for estado in af.estados:
        if estado not in manter:
            continue
        novo.add_estado(estado)
        for simbolo, destinos in af.transicoes[estado].items():
            for destino in destinos:
                if destino in manter:
                    novo.add_transicao(estado, simbolo, destino)
        for rotulo in af.finais.get(estado, []):
            novo.add_final(estado, rotulo)
    novo.alfabeto = list(af.alfabeto)
    return novo


def alcancaveis(af):
    visitados, pilha = {af.inicial}, [af.inicial]
    while pilha:
        for destinos in af.transicoes[pilha.pop()].values():
            for destino in destinos:
                if destino not in visitados:
                    visitados.add(destino)
                    pilha.append(destino)
    return visitados


def vivos(af):
    """Estados a partir dos quais algum estado final é alcançável."""
    vivos_ = set(af.finais)
    mudou = True
    while mudou:
        mudou = False
        for estado in af.estados:
            if estado in vivos_:
                continue
            if any(d in vivos_ for ds in af.transicoes[estado].values() for d in ds):
                vivos_.add(estado)
                mudou = True
    return vivos_


def remover_inalcancaveis(af):
    manter = alcancaveis(af)
    return restringir(af, manter), [e for e in af.estados if e not in manter]


def remover_mortos(af):
    manter = vivos(af) | {af.inicial}  # o inicial nunca é removido
    return restringir(af, manter), [e for e in af.estados if e not in manter]


# ---------------------------------------------------------------------------
# 4. Estado de erro
# ---------------------------------------------------------------------------

def adicionar_estado_erro(af):
    novo = restringir(af, set(af.estados))
    novo.add_estado(ESTADO_ERRO)
    novo.add_final(ESTADO_ERRO, ROTULO_ERRO)
    novo.prioridade.setdefault(ROTULO_ERRO, len(novo.prioridade))
    for estado in novo.estados:
        for simbolo in novo.alfabeto:
            if not novo.transicoes[estado].get(simbolo):
                novo.add_transicao(estado, simbolo, ESTADO_ERRO)
    return novo


# ---------------------------------------------------------------------------
# Pipeline, reconhecimento e saída
# ---------------------------------------------------------------------------

def gerar(texto, completo=True):
    """Executa todas as etapas e devolve um dicionário com cada AF."""
    afnd = carregar(texto)
    afd = determinizar(afnd, completo)
    sem_inalc, inalc = remover_inalcancaveis(afd)
    sem_mortos, mortos = remover_mortos(sem_inalc)
    final = adicionar_estado_erro(sem_mortos)
    return {
        "afnd": afnd,
        "afd": afd,
        "sem_inalcancaveis": sem_inalc,
        "inalcancaveis": inalc,
        "sem_mortos": sem_mortos,
        "mortos": mortos,
        "final": final,
    }


def reconhecer(afd, palavra):
    """Simula o AFD final. Devolve (estado, rótulo reconhecido ou None)."""
    estado = afd.inicial
    for simbolo in palavra:
        destinos = afd.transicoes[estado].get(simbolo)
        if not destinos:  # símbolo fora do alfabeto
            return ESTADO_ERRO, ROTULO_ERRO
        estado = next(iter(destinos))
    return estado, afd.rotulo(estado)


def tabela(af, markdown=False):
    cab = ["δ"] + [s if s != "|" else "\\|" if markdown else s for s in af.alfabeto]
    linhas = []
    for estado in af.estados:
        prefixo = ("→" if estado == af.inicial else "") + ("*" if estado in af.finais else "")
        linha = [prefixo + estado]
        for simbolo in af.alfabeto:
            destinos = af.transicoes[estado].get(simbolo, set())
            linha.append(", ".join(sorted(destinos, key=_ordem(af))) if destinos else "-")
        linhas.append(linha)
    if markdown:
        md = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
        md += ["| " + " | ".join(l) + " |" for l in linhas]
        return "\n".join(md)
    larguras = [max(len(str(x)) for x in col) for col in zip(cab, *linhas)]
    fmt = lambda l: "  ".join(str(x).ljust(w) for x, w in zip(l, larguras))
    return "\n".join([fmt(cab), fmt(["-" * w for w in larguras])] + [fmt(l) for l in linhas])


def _ordem(af):
    indice = {e: i for i, e in enumerate(af.estados)}
    return lambda e: indice.get(e, len(indice))


def descrever_finais(af):
    linhas = []
    for estado in af.estados:
        if estado in af.finais:
            todos = af.finais[estado]
            texto = f"  {estado}: {af.rotulo(estado)}"
            if len(todos) > 1:
                texto += f"   (também: {', '.join(r for r in todos if r != af.rotulo(estado))})"
            linhas.append(texto)
    return "\n".join(linhas)


def relatorio(res, markdown=False):
    titulo = (lambda t: f"\n## {t}\n") if markdown else (lambda t: f"\n=== {t} ===\n")
    finais = (lambda af: "Estados finais:\n\n```\n" + descrever_finais(af) + "\n```") if markdown \
        else (lambda af: "Estados finais:\n" + descrever_finais(af))
    partes = []
    for chave, nome in [("afnd", "AFND (carga)"),
                        ("afd", "AFD (determinização)"),
                        ("sem_inalcancaveis", "AFD sem estados inalcançáveis"),
                        ("sem_mortos", "AFD sem estados mortos"),
                        ("final", "AFD final (mínimo, com estado de erro)")]:
        af = res[chave]
        partes.append(titulo(nome))
        if chave == "afnd":
            partes.append(f"Determinístico: {'sim' if af.deterministico() else 'não'}\n")
        if chave == "sem_inalcancaveis":
            partes.append(f"Removidos: {', '.join(res['inalcancaveis']) or 'nenhum'}\n")
        if chave == "sem_mortos":
            partes.append(f"Removidos: {', '.join(res['mortos']) or 'nenhum'}\n")
        partes.append(tabela(af, markdown))
        partes.append("")
        partes.append(finais(af))
    return "\n".join(partes).strip() + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Gera AFD mínimo (sem classes de equivalência) a partir de tokens e GRs.")
    p.add_argument("entrada", help="arquivo texto com tokens e/ou GRs em BNF")
    p.add_argument("--saida", help="grava o relatório em Markdown neste arquivo")
    p.add_argument("--csv", help="grava a tabela do AFD final em CSV neste arquivo")
    p.add_argument("--so-alcancaveis", action="store_true",
                   help="na determinização, gera apenas estados alcançáveis a partir do inicial")
    p.add_argument("--testar", help="palavras separadas por espaço para reconhecer no AFD final")
    args = p.parse_args(argv)

    with open(args.entrada, encoding="utf-8") as f:
        res = gerar(f.read(), completo=not args.so_alcancaveis)

    print(relatorio(res))
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(f"# Resultado para `{args.entrada}`\n" + relatorio(res, markdown=True))
        print(f"Relatório gravado em {args.saida}")
    if args.csv:
        import csv
        af = res["final"]
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["estado", "inicial", "final", "rotulo"] + af.alfabeto)
            for e in af.estados:
                w.writerow([e, e == af.inicial, e in af.finais, af.rotulo(e) or ""]
                           + [next(iter(af.transicoes[e][s])) for s in af.alfabeto])
        print(f"Tabela CSV gravada em {args.csv}")
    if args.testar:
        print("\n=== Reconhecimento ===")
        for palavra in args.testar.split():
            estado, rotulo = reconhecer(res["final"], palavra)
            print(f"  {palavra!r:>12} -> estado {estado}: {rotulo or 'não aceita (estado não final)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
