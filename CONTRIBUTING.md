# Como contribuir

Obrigado pelo interesse em melhorar o **YouTube Clipper**! Este guia resume o
fluxo de trabalho, o padrão de código e o que esperamos de uma contribuição.

## Formas de contribuir

- Reportar bugs (use o template de *bug report*).
- Sugerir funcionalidades (use o template de *feature request*).
- Melhorar a documentação.
- Enviar código (correções, testes, novas funcionalidades).

## Antes de abrir uma issue

1. Procure nas [issues existentes](../../issues) por algo semelhante.
2. Se for um bug, reproduza com a versão mais recente e colete:
   - versão do app (aba **Ver Diagnóstico do Sistema**);
   - log em `%LOCALAPPDATA%\YouTubeClipper\logs\app.log`;
   - passos para reproduzir e o comportamento esperado.

## Configurando o ambiente

Requisitos: **Python 3.11+** (o CI roda 3.12) e Windows, Linux ou macOS.

```bash
git clone https://github.com/ariellaureanorosas/yt-clipper.git
cd yt-clipper
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements-dev.txt
pre-commit install
python main.py
```

O `ffmpeg`/`ffprobe` são baixados automaticamente na primeira execução. Para
rodar os testes não é necessário tê-los instalados.

## Fluxo de trabalho (Git)

1. Crie um branch a partir de `main`:
   `git switch -c fix/descricao-curta`
2. Faça mudanças pequenas e focadas.
3. Rode a suíte local (veja abaixo).
4. Faça commit usando [Conventional Commits](https://www.conventionalcommits.org/pt-br/):
   `fix: corrige cálculo de duração`, `feat: adiciona atalho`, `docs: ...`,
   `test: ...`, `chore: ...`.
5. Abra um Pull Request descrevendo **o problema** e **a solução**.

A branch `main` é protegida: todo código entra via Pull Request com CI verde.

## Padrões de código

- **Formatação:** [`black`](https://black.readthedocs.io/) (linha de 88, aspas
  simples preservadas).
- **Lint:** [`ruff`](https://docs.astral.sh/ruff/) com as regras `E`, `F`, `W`, `I`.
- **Tipagem:** anotações `from __future__ import annotations` e, quando útil,
  `dataclass(frozen=True, slots=True)` para objetos de valor.
- **Idioma:** nomes de domínio e mensagens em português; identificadores em
  inglês quando forem termos técnicos consagrados.
- **Erros:** não engula exceções silenciosamente; registre com `logger` e
  converta para mensagens que o usuário entenda.

Comandos:

```bash
pre-commit run --all-files     # roda tudo (recomendado)
ruff check .
black core ui tests main.py
python -m pytest -q
```

## Testes

- Todo comportamento novo deve ter teste em `tests/`.
- Prefira testes rápidos e determinísticos; **nunca** dependa de rede, GPU ou
  ffmpeg real (use `monkeypatch`/fakes, como nos testes existentes).
- O CI exige cobertura mínima de **55%** do pacote `core` (a UI Tkinter não é
  medida por ser difícil de testar de forma unitária).

## Pull Requests

Um bom PR:

- tem título claro (Conventional Commits);
- descreve o contexto e como testar;
- mantém o escopo pequeno;
- atualiza testes e, se necessário, `README.md`/`CHANGELOG.md`;
- passa em `ruff`, `black --check` e `pytest`.

O template de PR já traz um checklist — preencha-o.

## Segurança

Não abra issues públicas para vulnerabilidades. Siga o
[`SECURITY.md`](SECURITY.md).

## Licença

Ao contribuir, você concorda que sua contribuição será licenciada sob a
[MIT License](LICENSE).
