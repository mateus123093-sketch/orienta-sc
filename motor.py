"""
Motor de recomendação do Orienta SC.

A recomendação é determinística e explicável:
1. Calcula a afinidade do usuário com cada curso.
2. Cruza os cursos com os campi que realmente os oferecem na base.
3. Pontua cada combinação por custo, localização, ambiente e reputação.
4. Devolve os melhores cursos e as melhores faculdades, com justificativas.

Nada aqui inventa informação: tudo sai dos arquivos em dados/.
"""

import json
import math
from pathlib import Path

PASTA_DADOS = Path(__file__).parent / "dados"


def _carregar(nome: str):
    with open(PASTA_DADOS / nome, encoding="utf-8") as arquivo:
        return json.load(arquivo)


# Áreas que têm alguma proximidade entre si (para não zerar quem marcou
# uma área e tem perfil para outra).
AREAS_RELACIONADAS = {
    "Tecnologia": {"Engenharias"},
    "Engenharias": {"Tecnologia"},
    "Saúde": {"Agronegócio e Meio Ambiente"},
    "Agronegócio e Meio Ambiente": {"Saúde"},
    "Negócios": {"Direito e Sociais", "Comunicação e Artes", "Turismo e Gastronomia"},
    "Direito e Sociais": {"Negócios", "Educação"},
    "Educação": {"Direito e Sociais", "Comunicação e Artes"},
    "Comunicação e Artes": {"Negócios", "Educação", "Turismo e Gastronomia"},
    "Turismo e Gastronomia": {"Negócios", "Comunicação e Artes"},
}

ESTILOS_RELACIONADOS = {
    "pessoas": {"ideias"},
    "ideias": {"pessoas", "dados"},
    "dados": {"ideias", "coisas"},
    "coisas": {"dados"},
}

ROTULOS_ESTILO = {
    "pessoas": "trabalhar com pessoas",
    "dados": "trabalhar com dados e números",
    "ideias": "trabalhar com ideias e criação",
    "coisas": "trabalhar com coisas e processos",
}

ROTULOS_FORCA = {
    "exatas": "Exatas e cálculo",
    "bio": "Biologia e saúde",
    "leitura": "Leitura e escrita",
    "pessoas": "Pessoas e comunicação",
    "criatividade": "Criatividade e design",
    "organizacao": "Organização e planejamento",
    "tecnologia": "Tecnologia e lógica",
    "pratica": "Prática e mão na massa",
}

PESOS_PRIORIDADE = {
    "custo": {"financeiro": 0.45, "localizacao": 0.20, "social": 0.10, "qualidade": 0.25},
    "local": {"financeiro": 0.20, "localizacao": 0.50, "social": 0.10, "qualidade": 0.20},
    "qualidade": {"financeiro": 0.20, "localizacao": 0.15, "social": 0.10, "qualidade": 0.55},
    "social": {"financeiro": 0.15, "localizacao": 0.15, "social": 0.50, "qualidade": 0.20},
}

PORTES = ["pequeno", "medio", "grande"]
ROTULOS_PORTE = {"pequeno": "pequeno e acolhedor", "medio": "de porte médio", "grande": "grande e movimentado"}

# Programas de bolsa/financiamento aceitos pelo motor.
# "fator" é a fração da mensalidade que sobra para o aluno pagar (estimativa).
PROGRAMAS_BOLSA = {
    "prouni_integral": {"programa": "ProUni", "fator": 0.0, "rotulo": "ProUni 100%"},
    "prouni_parcial": {"programa": "ProUni", "fator": 0.5, "rotulo": "ProUni 50%"},
    "fies": {"programa": "FIES", "fator": 0.5, "rotulo": "FIES"},
}


def formatar_reais(valor: float) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


def distancia_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distância em linha reta entre duas coordenadas (fórmula de Haversine)."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


class Motor:
    def __init__(self) -> None:
        self.cursos = {c["id"]: c for c in _carregar("cursos.json")}
        self.instituicoes = _carregar("instituicoes.json")["instituicoes"]
        self.aviso_dados = _carregar("instituicoes.json")["aviso"]
        self.cidades = _carregar("cidades.json")

        # Índice: curso -> ofertas (instituição, campus)
        self.ofertas: dict[str, list[tuple[dict, dict]]] = {}
        for instituicao in self.instituicoes:
            for campus in instituicao["campi"]:
                for curso_id in campus["cursos"]:
                    if curso_id in self.cursos:
                        self.ofertas.setdefault(curso_id, []).append((instituicao, campus))

    # ------------------------------------------------------------------
    # Nota do curso (afinidade com o perfil)
    # ------------------------------------------------------------------
    def nota_curso(self, curso: dict, perfil: dict) -> tuple[float, list[str]]:
        nota = 0.0
        motivos: list[str] = []

        areas = set(perfil.get("areas", []))
        if curso["area"] in areas:
            nota += 50
            motivos.append(f"Combina com seu interesse em {curso['area'].lower()}")
        elif areas & AREAS_RELACIONADAS.get(curso["area"], set()):
            nota += 18

        forcas = set(perfil.get("forcas", []))
        em_comum = forcas & set(curso["forcas"])
        if em_comum:
            nota += min(30, 10 * len(em_comum))
            nomes = ", ".join(ROTULOS_FORCA[f].lower() for f in sorted(em_comum))
            motivos.append(f"Usa suas forças em {nomes}")

        estilo = perfil.get("estilo")
        if curso["estilo"] == estilo:
            nota += 20
            motivos.append(f"Combina com seu jeito de {ROTULOS_ESTILO[estilo]}")
        elif estilo in ESTILOS_RELACIONADOS.get(curso["estilo"], set()):
            nota += 8

        grau = perfil.get("grau", "tanto_faz")
        if grau == curso["grau"]:
            nota += 10
        elif grau == "tanto_faz":
            nota += 5

        return min(100.0, nota), motivos

    # ------------------------------------------------------------------
    # Nota da faculdade/campus para um curso
    # ------------------------------------------------------------------
    def nota_instituicao(self, instituicao: dict, campus: dict, curso: dict, perfil: dict):
        mensalidade_cheia = instituicao.get("custos", {}).get(curso["id"], instituicao["mensalidade"])
        orcamento = perfil.get("orcamento", 0)

        # Bolsa / financiamento: só entram instituições que participam do programa.
        programa = PROGRAMAS_BOLSA.get(perfil.get("financiamento", "nao"))
        bolsa_aplicada = None
        if mensalidade_cheia <= 0:
            bolsa_aplicada = "Gratuito"
            mensalidade = 0.0
        elif programa:
            if programa["programa"] not in instituicao.get("bolsas", []):
                return None  # instituição não participa do programa exigido
            mensalidade = mensalidade_cheia * programa["fator"]
            bolsa_aplicada = programa["rotulo"]
        else:
            mensalidade = mensalidade_cheia

        # Financeiro
        if mensalidade <= 0:
            financeiro = 100.0
            if bolsa_aplicada == "Gratuito":
                motivo_fin = "Instituição pública: curso gratuito"
            else:
                motivo_fin = f"{bolsa_aplicada}: mensalidade zerada (estimativa)"
        else:
            if orcamento <= 0:
                return None  # usuário precisa de curso gratuito
            razao = mensalidade / orcamento
            if razao <= 1:
                financeiro = 100.0
                situacao = "dentro do seu orçamento"
            elif razao <= 1.25:
                financeiro = 80.0
                situacao = "um pouco acima do orçamento"
            elif razao <= 1.6:
                financeiro = 55.0
                situacao = "acima do orçamento"
            elif razao <= 2.2:
                financeiro = 30.0
                situacao = "bem acima do orçamento"
            else:
                financeiro = 10.0
                situacao = "fora do seu orçamento"
            prefixo = f"Com {bolsa_aplicada}: " if bolsa_aplicada else ""
            motivo_fin = (
                f"{prefixo}mensalidade estimada de {formatar_reais(mensalidade)}/mês, {situacao}"
            )

        # Localização
        cidade_usuario = perfil.get("cidade")
        mobilidade = perfil.get("mobilidade", 0)
        if cidade_usuario in self.cidades and campus["cidade"] in self.cidades:
            dist = distancia_km(self.cidades[cidade_usuario], self.cidades[campus["cidade"]])
        else:
            dist = 0.0 if campus["cidade"] == cidade_usuario else 300.0

        if dist <= 1:
            localizacao = 100.0
            motivo_loc = "Fica na sua cidade"
        elif mobilidade >= 9999:
            localizacao = max(55.0, 95.0 - dist * 0.08)
            motivo_loc = f"A cerca de {dist:.0f} km de {cidade_usuario}"
        elif dist <= mobilidade:
            localizacao = 100.0 - 40.0 * (dist / max(mobilidade, 1))
            motivo_loc = f"A cerca de {dist:.0f} km de {cidade_usuario}, dentro do seu limite"
        else:
            return None  # fora do alcance que o usuário aceita

        # Ambiente / vida social
        porte = campus.get("porte", instituicao["porte"])
        ambiente = perfil.get("ambiente", "tanto_faz")
        if ambiente == "tanto_faz":
            social = 85.0
        elif ambiente == porte:
            social = 100.0
        elif abs(PORTES.index(ambiente) - PORTES.index(porte)) == 1:
            social = 65.0
        else:
            social = 35.0
        motivo_soc = f"Campus {ROTULOS_PORTE[porte]}"

        # Reputação/estrutura (estimativa da base, não ranking oficial)
        qualidade = float(instituicao["reputacao"])

        # Turno
        turnos = campus.get("turnos", instituicao.get("turnos", []))
        turno = perfil.get("turno", "flexivel")
        turno_ok = turno == "flexivel" or turno in turnos or "integral" in turnos

        pesos = PESOS_PRIORIDADE.get(perfil.get("prioridade", "custo"), PESOS_PRIORIDADE["custo"])
        nota_inst = (
            financeiro * pesos["financeiro"]
            + localizacao * pesos["localizacao"]
            + social * pesos["social"]
            + qualidade * pesos["qualidade"]
        )

        nota_curso, motivos_curso = self.nota_curso(curso, perfil)
        nota_final = 0.55 * nota_curso + 0.45 * nota_inst
        if not turno_ok:
            nota_final -= 6

        motivos = motivos_curso + [motivo_fin]
        if bolsa_aplicada and bolsa_aplicada != "Gratuito":
            motivos.append(
                f"Participa do {programa['programa']} — confirme vagas, renda e nota do Enem"
            )
        motivos += [motivo_loc, motivo_soc]
        if not turno_ok:
            motivos.append("Atenção: confirme o turno oferecido, ele pode não ser o que você procura")

        return {
            "instituicao": instituicao["nome"],
            "sigla": instituicao["sigla"],
            "tipo": instituicao["tipo"],
            "site": instituicao["site"],
            "bolsas": instituicao["bolsas"],
            "campus": campus["cidade"],
            "curso_id": curso["id"],
            "curso": curso["nome"],
            "grau": curso["grau"],
            "duracao": curso["duracao"],
            "mensalidade": round(mensalidade, 2),
            "mensalidade_cheia": round(mensalidade_cheia, 2),
            "bolsa_aplicada": bolsa_aplicada,
            "distancia_km": round(dist, 1),
            "nota_final": round(max(0.0, min(100.0, nota_final)), 1),
            "nota_curso": round(nota_curso, 1),
            "nota_instituicao": round(nota_inst, 1),
            "breakdown": {
                "financeiro": round(financeiro, 1),
                "localizacao": round(localizacao, 1),
                "social": round(social, 1),
                "qualidade": round(qualidade, 1),
            },
            "motivos": motivos[:5],
        }

    # ------------------------------------------------------------------
    # Recomendação completa
    # ------------------------------------------------------------------
    def recomendar(self, perfil: dict) -> dict:
        areas = set(perfil.get("areas", []))
        relacionadas = set().union(*(AREAS_RELACIONADAS.get(a, set()) for a in areas)) if areas else set()

        candidatos = [
            c for c in self.cursos.values()
            if not areas or c["area"] in areas or c["area"] in relacionadas
        ]
        if len(candidatos) < 3:
            candidatos = list(self.cursos.values())

        avaliados = []
        for curso in candidatos:
            nota, motivos = self.nota_curso(curso, perfil)
            avaliados.append((nota, curso, motivos))
        avaliados.sort(key=lambda item: item[0], reverse=True)

        top_cursos = avaliados[:5]

        # Cruza os cursos com as instituições que os oferecem.
        combinacoes = []
        for nota_curso, curso, motivos_curso in top_cursos:
            for instituicao, campus in self.ofertas.get(curso["id"], []):
                item = self.nota_instituicao(instituicao, campus, curso, perfil)
                if item:
                    combinacoes.append(item)

        combinacoes.sort(key=lambda item: item["nota_final"], reverse=True)

        # Diversifica: no máximo 2 por instituição e 2 por curso.
        escolhidas = []
        por_inst: dict[str, int] = {}
        por_curso: dict[str, int] = {}
        for item in combinacoes:
            if por_inst.get(item["sigla"], 0) >= 2:
                continue
            if por_curso.get(item["curso_id"], 0) >= 2:
                continue
            escolhidas.append(item)
            por_inst[item["sigla"]] = por_inst.get(item["sigla"], 0) + 1
            por_curso[item["curso_id"]] = por_curso.get(item["curso_id"], 0) + 1
            if len(escolhidas) == 6:
                break

        cursos_saida = []
        for nota, curso, motivos in top_cursos:
            cursos_saida.append({
                "id": curso["id"],
                "nome": curso["nome"],
                "area": curso["area"],
                "grau": curso["grau"],
                "duracao": curso["duracao"],
                "descricao": curso["descricao"],
                "carreiras": curso["carreiras"],
                "nota": round(nota, 1),
                "motivos": motivos,
                "faculdades": len(self.ofertas.get(curso["id"], [])),
            })

        avisos = []
        if perfil.get("orcamento") == 0 and perfil.get("financiamento") in (
            "prouni_parcial",
            "fies",
        ):
            avisos.append(
                "Você marcou que precisa de curso gratuito e também escolheu um programa "
                "que deixa mensalidade. Por isso as faculdades privadas ficaram de fora: "
                "nenhuma delas cabe em orçamento zero. Se puder pagar uma parte por mês, "
                "refaça a conversa com um orçamento maior."
            )

        return {
            "cursos": cursos_saida,
            "faculdades": escolhidas,
            "total_combinacoes": len(combinacoes),
            "avisos": avisos,
            "aviso": self.aviso_dados,
        }
