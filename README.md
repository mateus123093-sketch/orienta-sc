# Orienta SC

Site com chatbot que descobre qual curso superior combina com o usuário e quais
faculdades de Santa Catarina se encaixam no perfil dele — considerando custo,
localização, ambiente e reputação.

![Logo](static/logo.png)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mateus123093-sketch/orienta-sc)

## Como funciona

1. O chatbot faz 11 perguntas: cidade, mobilidade, áreas de interesse, pontos
   fortes, estilo de trabalho, orçamento, bolsa/financiamento, turno, tipo de
   campus, grau e prioridade.
2. O motor calcula a **afinidade com cada curso** (área + forças + estilo + grau).
3. Cruza os cursos com **apenas os campi que os oferecem** na base.
4. Pontua cada combinação por **financeiro, localização, ambiente e reputação**,
   com pesos que mudam conforme a prioridade escolhida.
5. Devolve os cursos e as faculdades com nota, justificativas e nota por critério.

A recomendação é determinística e explicável. O chatbot não inventa dados: tudo
sai de `dados/cursos.json` e `dados/instituicoes.json`.

## Rodar o projeto

```powershell
cd C:\Users\mateu\projects\orienta-sc
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Abra **http://127.0.0.1:8000**.

> Se o PowerShell bloquear a ativação:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Deploy gratuito

O projeto já vem com os arquivos de deploy: `render.yaml` (Render) e `Dockerfile`
(funciona em qualquer host que aceite container).

Antes de qualquer coisa, coloque o projeto num repositório Git:

```powershell
cd C:\Users\mateu\projects\orienta-sc
git init
git add .
git commit -m "Orienta SC"
```

E publique no GitHub (crie um repositório vazio em github.com/new):

```powershell
git remote add origin https://github.com/SEU-USUARIO/orienta-sc.git
git branch -M main
git push -u origin main
```

### Opção 1 — Render (mais simples, grátis)

Atalho: abra **https://render.com/deploy?repo=https://github.com/mateus123093-sketch/orienta-sc**
— o Render já abre com o `render.yaml` lido e só pede para confirmar.

Ou, pelo painel:

1. Crie uma conta em [render.com](https://render.com) e conecte o GitHub.
2. **New → Blueprint** e escolha o repositório `orienta-sc`.
3. O Render lê o `render.yaml` e cria o serviço sozinho. Só confirmar.
4. Em ~3 minutos o site fica em `https://orienta-sc.onrender.com`.

Detalhes do plano free: a instância **dorme após 15 minutos sem acesso** e a
primeira visita depois disso demora ~50 segundos para responder. Para um site de
demonstração, é o suficiente.

### Opção 2 — Hugging Face Spaces (grátis, sem dormir por 48h)

1. Crie uma conta em [huggingface.co](https://huggingface.co).
2. **New Space → Docker → Blank**.
3. Envie os arquivos do projeto (ou conecte o repositório GitHub pelo botão
   *Files → Import*).
4. O Space usa o `Dockerfile` e sobe na porta 7860 automaticamente.

### Opção 3 — Koyeb / Fly.io (grátis, com cartão)

Os dois leem o mesmo `Dockerfile`. No Koyeb: **Create Service → GitHub → Dockerfile**,
porta `7860`, instância `Free`. No Fly.io: `fly launch` na pasta do projeto.

### Cuidados ao publicar

- **Sessões em memória:** o app guarda as respostas na RAM. Funciona porque o
  deploy usa **1 worker**. Se um dia escalar para mais de uma instância, troque
  `sessoes` por Redis ou banco de dados.
- **Dados demonstrativos:** veja o aviso no fim deste README antes de divulgar.
- **LGPD:** o chat não pede nome, e-mail, CPF nem telefone. Mantenha assim.
- **Domínio próprio:** no Render, em *Settings → Custom Domain*; é grátis, só
  precisa do DNS do seu domínio.

## Estrutura

```
orienta-sc/
├── app.py                  # FastAPI: rotas, perguntas e sessões
├── motor.py                # motor de recomendação e notas
├── dados/
│   ├── cursos.json         # 49 cursos com área, forças e estilo
│   ├── instituicoes.json   # 16 instituições e 82 campi de SC
│   └── cidades.json        # cidades de SC + coordenadas
├── static/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── logo.png
├── requirements.txt
├── render.yaml             # deploy no Render (plano free)
├── Dockerfile              # deploy em qualquer host de container
└── README.md
```

## Editar a base

### Cursos (`dados/cursos.json`)

```json
{
  "id": "ciencia-computacao",
  "nome": "Ciência da Computação",
  "area": "Tecnologia",
  "grau": "Bacharelado",
  "duracao": "4 anos",
  "estilo": "dados",
  "forcas": ["exatas", "tecnologia", "organizacao"],
  "descricao": "...",
  "carreiras": ["...", "..."]
}
```

Valores aceitos:

- `area`: Tecnologia, Saúde, Engenharias, Negócios, Educação, Direito e Sociais,
  Comunicação e Artes, Agronegócio e Meio Ambiente, Turismo e Gastronomia
- `grau`: Bacharelado, Licenciatura, Tecnólogo
- `estilo`: pessoas, dados, ideias, coisas
- `forcas`: exatas, bio, leitura, pessoas, criatividade, organizacao, tecnologia, pratica

### Instituições (`dados/instituicoes.json`)

Cada instituição tem `campi`, e cada campus lista os IDs dos cursos que oferece:

```json
{
  "id": "ufsc",
  "nome": "Universidade Federal de Santa Catarina",
  "sigla": "UFSC",
  "tipo": "publica",
  "reputacao": 96,
  "mensalidade": 0,
  "bolsas": ["Gratuito"],
  "site": "https://ufsc.br",
  "porte": "grande",
  "turnos": ["manha", "tarde", "integral", "noite"],
  "campi": [
    { "cidade": "Florianópolis", "cursos": ["medicina", "direito", "eng-civil"] }
  ]
}
```

- `tipo`: `publica`, `privada` ou `comunitaria`
- `porte`: `pequeno`, `medio` ou `grande`
- `mensalidade`: valor médio estimado (0 para públicas)
- `custos`: opcional, para sobrescrever o valor de cursos específicos
  (ex.: `{"medicina": 5200}`)
- A cidade do campus precisa existir em `dados/cidades.json` (é de lá que vêm
  as coordenadas usadas no cálculo de distância).

### Cidades (`dados/cidades.json`)

```json
{ "Florianópolis": [-27.5954, -48.5480] }
```

Adicione a cidade com latitude e longitude para que ela apareça no chatbot e
entre no cálculo de distância.

## Como a nota é calculada

**Curso (0–100):**

- 50 pontos por área de interesse (18 se for área relacionada)
- até 30 pontos por pontos fortes em comum
- 20 pontos por estilo de trabalho compatível (8 se relacionado)
- 10 pontos por grau compatível

**Faculdade/campus (0–100):**

- Financeiro: gratuito = 100; mensalidade comparada ao orçamento
- Localização: distância real (Haversine) e limite de mobilidade
- Ambiente: porte do campus vs. preferência
- Reputação: campo `reputacao` da base (estimativa, não ranking oficial)

**Nota final:** 55% curso + 45% faculdade, com pesos diferentes conforme a
prioridade (custo, localização, qualidade ou vida social).

Combinações fora do orçamento (quando o usuário precisa de curso gratuito) ou
fora do limite de distância são descartadas.

### Filtro de bolsa e financiamento

Quando o usuário escolhe um programa, o motor **descarta** instituições que não o
oferecem (públicas continuam sempre elegíveis, porque são gratuitas) e aplica um
fator sobre a mensalidade para calcular o custo real:

| Resposta | Programa exigido | Fator sobre a mensalidade |
| --- | --- | --- |
| Não preciso / não sei | — | 1,0 (valor cheio) |
| ProUni — bolsa integral | ProUni | 0,0 |
| ProUni — bolsa parcial | ProUni | 0,5 |
| FIES — financiamento | FIES | 0,5 |

Os fatores são **estimativas de planejamento**, não regras oficiais. Na prática,
ProUni e FIES dependem da renda familiar, da nota do Enem e da quantidade de vagas
do curso naquela instituição. A interface sempre mostra a mensalidade cheia ao
lado da mensalidade com bolsa para deixar isso explícito.

Para que o filtro funcione, o campo `bolsas` de cada instituição precisa listar os
programas aceitos (`"ProUni"`, `"FIES"`, `"Bolsas próprias"`, `"Gratuito"`).

Quando a pessoa escolhe **curso gratuito** e depois ProUni parcial ou FIES, a
interface avisa em dois momentos: na própria pergunta (explicando que ainda sobra
mensalidade) e no resultado (explicando por que nenhuma faculdade privada
apareceu). Sem o aviso, a lista só com públicas parecia um erro.

## Aviso sobre os dados

A base atual é **demonstrativa**. Cursos oferecidos por campus, turnos,
mensalidades e notas de reputação são estimativas e precisam ser validados nos
sites oficiais antes de publicar o site para o público.

Sugestões para produção:

- Substituir a base por dados oficiais (e-MEC/INEP, sites das instituições)
- Guardar as sessões em banco (hoje ficam em memória)
- Adicionar autenticação/limite de uso se for expor publicamente
- Revisar a LGPD: não pedir dados pessoais no chat

## Próximos passos possíveis

- Calculadora de financiamento (parcela pós-formatura do FIES)
- Comparador lado a lado de faculdades
- Exportar resultado em PDF
- Versão com IA generativa para explicar o resultado em linguagem natural
- Base oficial de ofertas por campus (e-MEC/INEP) com atualização automática
