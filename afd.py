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

## Secao para determinação de automatos

def determinizar(afdn):
    afd = afdn.copia_vazia()
    


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

