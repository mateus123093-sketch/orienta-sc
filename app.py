"""
Orienta SC — site de orientação vocacional para cursos superiores em SC.

Backend FastAPI:
- serve a página (static/)
- conduz a conversa do chatbot (perguntas em sequência)
- chama o motor de recomendação com as respostas do perfil
"""

import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from motor import Motor

BASE_DIR = Path(__file__).parent
motor = Motor()

app = FastAPI(title="Orienta SC", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# ---------------------------------------------------------------------------
# Perguntas do chatbot
# ---------------------------------------------------------------------------

AREAS = [
    ("Tecnologia", "Programação, dados, IA, redes e sistemas"),
    ("Saúde", "Cuidar de pessoas, corpo humano e bem-estar"),
    ("Engenharias", "Construir, projetar e resolver problemas técnicos"),
    ("Negócios", "Empresas, finanças, gestão e empreendedorismo"),
    ("Educação", "Ensinar, pesquisar e trabalhar com conhecimento"),
    ("Direito e Sociais", "Leis, sociedade, política e causas coletivas"),
    ("Comunicação e Artes", "Criar, escrever, comunicar e produzir conteúdo"),
    ("Agronegócio e Meio Ambiente", "Campo, animais, natureza e sustentabilidade"),
    ("Turismo e Gastronomia", "Viagens, hospitalidade, comida e experiências"),
]

FORCAS = [
    ("exatas", "Exatas e cálculo", "Gosto de matemática, lógica e números"),
    ("bio", "Biologia e saúde", "Tenho interesse pelo corpo humano e pela natureza"),
    ("leitura", "Leitura e escrita", "Gosto de ler, interpretar e escrever"),
    ("pessoas", "Pessoas e comunicação", "Gosto de conversar, ajudar e trabalhar em equipe"),
    ("criatividade", "Criatividade e design", "Gosto de criar, desenhar e imaginar soluções"),
    ("organizacao", "Organização e planejamento", "Gosto de planejar, organizar e liderar"),
    ("tecnologia", "Tecnologia e lógica", "Gosto de computadores, sistemas e inovação"),
    ("pratica", "Prática e mão na massa", "Prefiro aprender fazendo e resolver coisas concretas"),
]

PERGUNTAS = [
    {
        "id": "cidade",
        "campo": "cidade",
        "tipo": "cidade",
        "texto": "Primeiro, onde você mora?",
        "subtitulo": "Uso sua cidade para calcular a distância até cada campus.",
        "opcoes": [{"valor": cidade, "rotulo": cidade} for cidade in sorted(motor.cidades)],
    },
    {
        "id": "mobilidade",
        "campo": "mobilidade",
        "tipo": "single",
        "texto": "Quanto você está disposto(a) a se deslocar para estudar?",
        "subtitulo": "Considere o trajeto diário ou a possibilidade de morar em outra cidade.",
        "opcoes": [
            {"valor": 0, "rotulo": "Só na minha cidade"},
            {"valor": 50, "rotulo": "Até 50 km"},
            {"valor": 150, "rotulo": "Até 150 km"},
            {"valor": 9999, "rotulo": "Posso morar em outra região"},
        ],
    },
    {
        "id": "areas",
        "campo": "areas",
        "tipo": "multi",
        "texto": "Quais áreas mais despertam seu interesse?",
        "subtitulo": "Escolha até 2. Não precisa ter certeza — é só um ponto de partida.",
        "max": 2,
        "opcoes": [{"valor": nome, "rotulo": nome, "descricao": desc} for nome, desc in AREAS],
    },
    {
        "id": "forcas",
        "campo": "forcas",
        "tipo": "multi",
        "texto": "Em quais matérias ou atividades você se dá melhor?",
        "subtitulo": "Escolha até 3. Pense no que você faz bem e gosta de fazer.",
        "max": 3,
        "opcoes": [{"valor": valor, "rotulo": nome, "descricao": desc} for valor, nome, desc in FORCAS],
    },
    {
        "id": "estilo",
        "campo": "estilo",
        "tipo": "single",
        "texto": "Como você prefere trabalhar no dia a dia?",
        "subtitulo": "Não existe resposta certa — o ideal é o curso combinar com seu jeito.",
        "opcoes": [
            {"valor": "pessoas", "rotulo": "Com pessoas", "descricao": "Atender, ensinar, cuidar, conversar"},
            {"valor": "dados", "rotulo": "Com dados e números", "descricao": "Analisar, calcular, programar"},
            {"valor": "ideias", "rotulo": "Com ideias e criação", "descricao": "Criar, escrever, projetar, argumentar"},
            {"valor": "coisas", "rotulo": "Com coisas e processos", "descricao": "Construir, operar, organizar, produzir"},
        ],
    },
    {
        "id": "orcamento",
        "campo": "orcamento",
        "tipo": "single",
        "texto": "Quanto você consegue investir por mês na mensalidade?",
        "subtitulo": "Se precisar de curso gratuito, escolha a primeira opção. Bolsas e FIES podem mudar esse cenário.",
        "opcoes": [
            {"valor": 0, "rotulo": "Preciso de curso gratuito"},
            {"valor": 600, "rotulo": "Até R$ 600"},
            {"valor": 1000, "rotulo": "Até R$ 1.000"},
            {"valor": 1500, "rotulo": "Até R$ 1.500"},
            {"valor": 9999, "rotulo": "Acima de R$ 1.500"},
        ],
    },
    {
        "id": "financiamento",
        "campo": "financiamento",
        "tipo": "single",
        "texto": "Pretende usar bolsa ou financiamento estudantil?",
        "subtitulo": "Mostro só faculdades que participam do programa que você escolher. As regras reais dependem da sua renda e da nota do Enem.",
        "opcoes": [
            {"valor": "nao", "rotulo": "Não preciso / não sei", "descricao": "Ver todas as faculdades"},
            {"valor": "prouni_integral", "rotulo": "ProUni — bolsa integral", "descricao": "Mensalidade zerada nas faculdades participantes"},
            {"valor": "prouni_parcial", "rotulo": "ProUni — bolsa parcial", "descricao": "Pago cerca de metade da mensalidade"},
            {"valor": "fies", "rotulo": "FIES — financiamento", "descricao": "Financio parte do curso e pago depois de formado"},
        ],
    },
    {
        "id": "turno",
        "campo": "turno",
        "tipo": "single",
        "texto": "Qual turno funciona melhor para você?",
        "subtitulo": "Alguns cursos existem em apenas um turno na instituição.",
        "opcoes": [
            {"valor": "manha", "rotulo": "Manhã"},
            {"valor": "tarde", "rotulo": "Tarde"},
            {"valor": "noite", "rotulo": "Noite"},
            {"valor": "flexivel", "rotulo": "Tanto faz / integral"},
        ],
    },
    {
        "id": "ambiente",
        "campo": "ambiente",
        "tipo": "single",
        "texto": "Que tipo de campus combina com você?",
        "subtitulo": "Isso ajuda a escolher entre uma universidade grande e um campus menor.",
        "opcoes": [
            {"valor": "grande", "rotulo": "Grande e movimentado", "descricao": "Muitos cursos, eventos e vida estudantil"},
            {"valor": "medio", "rotulo": "Médio e equilibrado", "descricao": "Estrutura boa sem ser gigante"},
            {"valor": "pequeno", "rotulo": "Pequeno e acolhedor", "descricao": "Turmas menores e mais proximidade"},
            {"valor": "tanto_faz", "rotulo": "Tanto faz", "descricao": "Quero priorizar outros fatores"},
        ],
    },
    {
        "id": "grau",
        "campo": "grau",
        "tipo": "single",
        "texto": "Que tipo de graduação combina com seu momento?",
        "subtitulo": "Bacharelado é mais amplo; licenciatura forma professores; tecnólogo é mais curto e prático.",
        "opcoes": [
            {"valor": "Bacharelado", "rotulo": "Bacharelado", "descricao": "4 a 6 anos, formação ampla"},
            {"valor": "Licenciatura", "rotulo": "Licenciatura", "descricao": "Para dar aula, 4 anos"},
            {"valor": "Tecnólogo", "rotulo": "Tecnólogo", "descricao": "2 a 3 anos, foco no mercado"},
            {"valor": "tanto_faz", "rotulo": "Tanto faz", "descricao": "Quero ver todas as opções"},
        ],
    },
    {
        "id": "prioridade",
        "campo": "prioridade",
        "tipo": "single",
        "texto": "Por último: o que mais pesa na sua escolha?",
        "subtitulo": "Vou usar isso para ajustar o peso de custo, distância, ambiente e reputação.",
        "opcoes": [
            {"valor": "custo", "rotulo": "Menor custo", "descricao": "Mensalidade, bolsas e transporte"},
            {"valor": "local", "rotulo": "Perto de casa", "descricao": "Menos deslocamento no dia a dia"},
            {"valor": "qualidade", "rotulo": "Reputação e qualidade", "descricao": "Tradição, estrutura e corpo docente"},
            {"valor": "social", "rotulo": "Vida social e estrutura", "descricao": "Campus, eventos, esporte e convivência"},
        ],
    },
]

ROTULOS = {
    "cidade": "Cidade",
    "mobilidade": "Deslocamento",
    "areas": "Áreas de interesse",
    "forcas": "Pontos fortes",
    "estilo": "Jeito de trabalhar",
    "orcamento": "Orçamento",
    "financiamento": "Bolsa/Financiamento",
    "turno": "Turno",
    "ambiente": "Campus",
    "grau": "Graduação",
    "prioridade": "Prioridade",
}


def _rotulo_opcao(pergunta: dict, valor) -> str:
    for opcao in pergunta.get("opcoes", []):
        if opcao["valor"] == valor:
            return opcao["rotulo"]
    return str(valor)


def resumo_perfil(respostas: dict) -> list[dict]:
    resumo = []
    for pergunta in PERGUNTAS:
        campo = pergunta["campo"]
        if campo not in respostas:
            continue
        valor = respostas[campo]
        if isinstance(valor, list):
            texto = ", ".join(_rotulo_opcao(pergunta, v) for v in valor)
        else:
            texto = _rotulo_opcao(pergunta, valor)
        resumo.append({"campo": campo, "rotulo": ROTULOS[campo], "valor": texto})
    return resumo


# ---------------------------------------------------------------------------
# Sessões
# ---------------------------------------------------------------------------

class Sessao:
    def __init__(self) -> None:
        self.respostas: dict = {}
        self.indice = 0
        self.resultado: dict | None = None


sessoes: dict[str, Sessao] = {}
trava = threading.Lock()


def _pergunta_atual(sessao: Sessao) -> dict | None:
    if sessao.indice >= len(PERGUNTAS):
        return None
    return PERGUNTAS[sessao.indice]


def _estado(sessao_id: str, sessao: Sessao) -> dict:
    pergunta = _pergunta_atual(sessao)
    estado = {
        "sessao_id": sessao_id,
        "tipo": "pergunta" if pergunta else "resultado",
        "pergunta": pergunta,
        "progresso": {
            "atual": min(sessao.indice + 1, len(PERGUNTAS)),
            "total": len(PERGUNTAS),
        },
        "resumo": resumo_perfil(sessao.respostas),
    }
    if not pergunta and sessao.resultado:
        estado["resultado"] = sessao.resultado
    return estado


def _validar(pergunta: dict, valor):
    opcoes = pergunta.get("opcoes", [])
    validos = [o["valor"] for o in opcoes]

    if pergunta["tipo"] == "multi":
        if not isinstance(valor, list) or not valor:
            raise HTTPException(400, "Escolha pelo menos uma opção.")
        if len(valor) > pergunta.get("max", len(opcoes)):
            raise HTTPException(400, f"Escolha no máximo {pergunta['max']} opções.")
        if any(v not in validos for v in valor):
            raise HTTPException(400, "Opção inválida.")
        return valor

    if isinstance(valor, list):
        raise HTTPException(400, "Escolha apenas uma opção.")
    if valor not in validos:
        raise HTTPException(400, "Opção inválida.")
    return valor


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "cursos": len(motor.cursos), "instituicoes": len(motor.instituicoes)}


class Resposta(BaseModel):
    valor: Any


@app.post("/api/sessao")
def criar_sessao():
    sessao_id = uuid.uuid4().hex
    sessao = Sessao()
    with trava:
        sessoes[sessao_id] = sessao
    return _estado(sessao_id, sessao)


@app.get("/api/sessao/{sessao_id}")
def obter_sessao(sessao_id: str):
    with trava:
        sessao = sessoes.get(sessao_id)
    if not sessao:
        raise HTTPException(404, "Sessão não encontrada. Comece de novo.")
    return _estado(sessao_id, sessao)


@app.post("/api/sessao/{sessao_id}/resposta")
def responder(sessao_id: str, corpo: Resposta):
    with trava:
        sessao = sessoes.get(sessao_id)
        if not sessao:
            raise HTTPException(404, "Sessão não encontrada. Comece de novo.")

        pergunta = _pergunta_atual(sessao)
        if not pergunta:
            raise HTTPException(400, "Esta sessão já foi concluída.")

        valor = _validar(pergunta, corpo.valor)
        sessao.respostas[pergunta["campo"]] = valor
        sessao.indice += 1

        if _pergunta_atual(sessao):
            return _estado(sessao_id, sessao)

        resultado = motor.recomendar(sessao.respostas)
        resultado["resumo"] = resumo_perfil(sessao.respostas)
        sessao.resultado = resultado
        return {"sessao_id": sessao_id, "tipo": "resultado", "resultado": resultado}


@app.post("/api/sessao/{sessao_id}/reiniciar")
def reiniciar(sessao_id: str):
    with trava:
        sessao = sessoes.get(sessao_id)
        if not sessao:
            raise HTTPException(404, "Sessão não encontrada.")
        sessao.respostas = {}
        sessao.indice = 0
        sessao.resultado = None
    return _estado(sessao_id, sessao)
