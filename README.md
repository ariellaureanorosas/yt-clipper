# 🎬 YouTube Clipper

[![CI](https://github.com/ariellaureanorosas/yt-clipper/actions/workflows/ci.yml/badge.svg)](https://github.com/ariellaureanorosas/yt-clipper/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ariellaureanorosas/yt-clipper?label=release)](https://github.com/ariellaureanorosas/yt-clipper/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Baixe vídeos do YouTube, corte trechos e converta para formato **vertical (9:16, para TikTok/Shorts/Reels)** ou **horizontal (16:9, para YouTube)** — tudo em um programa simples, com botões.

> Você não precisa saber programar. Siga o passo a passo abaixo.
>
> **Requisitos mínimos:** Windows 10/11 (64-bit) e 8 GB de RAM. Em PCs com
> pouca memória o app ativa automaticamente o modo econômico.

---

## ✅ Como instalar (passo a passo)

### Antes de começar
- Você precisa de **Windows 10 ou 11 (64-bit)**.
- Precisa de **internet** apenas para baixar o instalador (~85 MB).

### Passo 1 — Baixar o instalador

Abra a página de
[**Releases**](https://github.com/ariellaureanorosas/yt-clipper/releases/latest),
baixe `YouTubeClipper-Setup-<versão>.exe` e execute.

O instalador já inclui **tudo** o que o programa precisa (Python, yt-dlp e
ffmpeg). Você **não** precisa instalar nada antes nem baixar dependências
depois — a primeira execução é imediata.

### Passo 2 — Instalar

1. Clique **duas vezes** no arquivo baixado.
2. Se o Windows mostrar o aviso azul ("Windows protegeu o computador"), clique
   em **"Mais informações"** e depois em **"Executar assim mesmo"** — o
   programa ainda não possui assinatura digital.
3. Siga o assistente. A instalação é feita **só para o seu usuário**, em
   `%LOCALAPPDATA%\Programs\YouTubeClipper`, e **não pede senha de administrador**.
4. Ao final, o programa abre automaticamente. O atalho **"YouTube Clipper"**
   fica no **Menu Iniciar** e na **Área de Trabalho**.

### Atualizações automáticas

A partir da versão **1.3.1**, o programa se atualiza sozinho com supervisão:

- Ao abrir, ele verifica se existe uma versão mais nova publicada.
- Se existir, mostra o que mudou e pergunta se você quer atualizar.
- O download acontece em segundo plano e é validado (tamanho, cabeçalho de
  executável e SHA-256 quando a release publica o checksum).
- Ao terminar, um **supervisor externo** espera o app fechar de verdade, faz um
  backup rápido da instalação, executa o Setup **no mesmo local**, confere a
  versão instalada e **reabre o aplicativo já atualizado**.
- Se a instalação falhar, o supervisor **restaura a versão anterior**, registra
  o motivo e o app mostra o erro na próxima abertura. A mesma versão não é
  oferecida de novo por 24 h (a verificação manual continua disponível).
- Logs em `%LOCALAPPDATA%\YouTubeClipper\logs` (`app.log` e `update-*.log`).

> Quem está na **v1.3.0 ou anterior** precisa baixar este Setup **uma única
> vez**. Das próximas em diante, a atualização é automática.

---

## 🎮 Como usar o programa

1. **Cole o link do vídeo** do YouTube no campo lá de cima. Pode colar o link normal (`https://www.youtube.com/watch?v=...`) ou o link gerado pelo botão **Compartilhar** do YouTube — funcionam `https://youtu.be/...`, `https://www.youtube.com/live/...` (lives/estreias), Shorts, links do celular (`m.youtube.com`) e vídeos incorporados. O `?si=...` no final não atrapalha.
2. Clique em **Carregar**. O programa mostra o título do vídeo, a duração e a miniatura.
3. **Escolha o formato:**
   - **Horizontal (1920×1080)** — formato normal, para YouTube.
   - **Vertical (1080×1920)** — formato de celular, para Shorts/TikTok/Reels.
4. **Escolha o trecho** (início e fim) usando as barrinhas deslizantes ou digitando o tempo (`00:01:30`).
5. Clique no botão **Selecionar** (ao lado de *Pasta de salvamento*) para escolher onde salvar o vídeo. Você também pode digitar o caminho na caixinha.
6. Clique no botão **Processar**.
7. Espere a barra de progresso chegar a 100%. Pronto! Seu vídeo recortado está na pasta escolhida. ✅

> 💡 Dica: quanto menor o trecho, mais rápido fica pronto. Cortes que não mudam o formato são quase instantâneos.
>
> ✅ O **ffmpeg** já vem incluído no instalador — não há download na primeira execução.

---

## ❓ Problemas comuns

### "Windows impediu a execução" (tela azul)
O Windows às vezes desconfia de programas recém-criados. Clique em **"Mais informações"** e depois em **"Executar assim mesmo"**.

### A janela do instalador fecha sozinha e não cria o atalho
Feche antivírus/otimizadores temporariamente e execute o `YouTubeClipper-Setup-<versão>.exe` novamente. Se o Windows bloquear o arquivo, clique com o botão direito → **Propriedades** → marque **"Desbloquear"** → **Aplicar**.

### "Não foi possível baixar o ffmpeg"
Esse aviso não deve aparecer na versão instalada (o ffmpeg vai embutido). Se aparecer, reinstale pelo Setup para restaurar os arquivos.

### Erro de download: "The read operation timed out"
A conexão com o YouTube ficou lenta ou instável. O programa já tenta novamente até 5 vezes automaticamente. Se continuar:
1. Teste a internet e desative VPN/proxy.
2. Evite horários de pico ou vídeos muito longos.
3. Para redes muito instáveis, aumente os limites pelas variáveis de ambiente (`YTCLIPPER_DL_RETRIES`, `YTCLIPPER_DL_SOCKET_TIMEOUT`) — veja a seção de desenvolvedores.

### Erro ao cortar vídeo (`ffmpeg code ...`) em PCs com 8 GB de RAM
Isso normalmente é **falta de memória** (o Windows encerra o ffmpeg). No computador do usuário:
1. Feche navegador, jogos e outros programas pesados antes de processar.
2. Em **Opções avançadas**, marque **"Forçar encoding por CPU"** — evita tentativas de GPU incompatíveis (ex.: AMD sem NVENC) e usa o modo econômico de memória.
3. Prefira trechos mais curtos e o formato **Horizontal** quando o vídeo original já for 16:9.
4. Clique em **"Ver Diagnóstico do Sistema"** e envie o texto junto do log ao reportar o problema.

### O programa não abre
Feche e abra de novo. Se continuar, execute o `YouTubeClipper-Setup-<versão>.exe` novamente (ele reinstala por cima, mantendo suas configurações e logs).

---

## 💻 Informações para desenvolvedores

**Tecnologias:** Python 3.11+ + CustomTkinter (interface), yt-dlp (download), ffmpeg (corte/conversão).

O app detecta o hardware na inicialização (GPU/encoders disponíveis, RAM, CPU) e escolhe o melhor pipeline de encoding, com fallback automático para CPU. Um modo de **economia de memória** (threads e filas reduzidas) é aplicado automaticamente quando há pouca RAM disponível.

### Perfis de hardware

| Perfil | Quando é usado | Efeito |
|--------|----------------|--------|
| `high_end` | 32 GB+ RAM e GPU dedicada | Presets mais rápidos/qualidade, paralelismo alto |
| `mid_range` | 16 GB+ RAM | Equilíbrio padrão |
| `low_memory` | Menos de 16 GB RAM / pouca RAM livre | Threads=2, filas menores, chunk de download menor |
| `ci_cd` | Testes/CI | Determinístico, sem depender de GPU |

### Configuração por variáveis de ambiente

Todas são opcionais; os defaults funcionam sem configuração.

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `YTCLIPPER_PROFILE` | auto | `high_end`, `mid_range`, `low_memory` ou `ci_cd`. Sem valor, o perfil é detectado pelo hardware |
| `YTCLIPPER_LOW_MEMORY` | `false` | `true` força o modo de economia de memória |
| `YTCLIPPER_PREFER_HW` | auto | `false` força encoding por CPU; `true` força tentativa de GPU |
| `YTCLIPPER_DL_SOCKET_TIMEOUT` | `60` | Timeout de socket do download (segundos) |
| `YTCLIPPER_DL_RETRIES` | `5` | Número de tentativas de download |
| `YTCLIPPER_DL_CHUNK_SIZE` | `10485760` | Tamanho do chunk HTTP (bytes) |
| `YTCLIPPER_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `YTCLIPPER_CHECK_UPDATES` | `true` | `false` desliga a atualização automática |
| `YTCLIPPER_UPDATE_CHECK_ON_START` | `true` | `false` não verifica ao abrir (o botão manual continua disponível) |
| `YTCLIPPER_UPDATE_TIMEOUT` | `8` | Timeout das requisições de atualização (segundos) |

### Rodar em modo desenvolvimento

Requisitos: **Python 3.11+** (o CI usa 3.12).

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1  |  Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install   # opcional, mas recomendado
python main.py
```

### Testes e qualidade de código

```bash
pytest                       # testes + cobertura (mínimo de 55% em core)
ruff check .                 # lint (imports, nomes, erros)
black core ui tests main.py  # formatação
pre-commit run --all-files   # tudo de uma vez
```

O repositório tem CI (GitHub Actions) que roda lint, formatação e testes a cada
push/PR na branch `main`. A branch é protegida: mudanças entram por Pull
Request com os checks **Lint e formatação** e **Testes** verdes.

Contribuições são bem-vindas — leia o [`CONTRIBUTING.md`](CONTRIBUTING.md) e o
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Para falhas de segurança, siga o
[`SECURITY.md`](SECURITY.md) (não abra issue pública). O histórico de mudanças
fica no [`CHANGELOG.md`](CHANGELOG.md).

### Logs

Em caso de erro, o aplicativo grava um log de diagnóstico em:

```
%LOCALAPPDATA%\YouTubeClipper\logs\app.log
```

### Gerar o executável e o instalador

```bash
# 1) pasta dist/YouTubeClipper (exe + dependências + ffmpeg embutido)
pyinstaller --clean --noconfirm build.spec

# 2) instalador dist/installer/YouTubeClipper-Setup-<versão>.exe
ISCC.exe /DAppVersion=1.3.0 installer\ytclipper.iss
```

O ffmpeg/ffprobe precisam estar em `assets/` antes do passo 1 (o CI baixa
automaticamente; localmente, coloque os dois `.exe` na pasta). O script
`tools/make_icons.py` regenera `icons/app.png` e `icons/app.ico` a partir da
arte, com fundo transparente.

### Publicar uma nova versão (para o auto-update chegar aos usuários)

1. Atualize `__version__` em `core/__init__.py` (ex.: `1.3.0`) e o `CHANGELOG.md`.
2. Faça commit e push na `main`.
3. Crie e envie a tag correspondente:

```bash
git tag v1.3.0
git push origin v1.3.0
```

O workflow de release valida que a tag e o `__version__` são iguais, roda os
testes, baixa o ffmpeg, compila o app, gera o instalador e o `.sha256` e publica
na Release. O aplicativo dos usuários detecta essa Release na próxima abertura
e se atualiza.


### Correção (corte sem travamento no início)

O corte por *stream copy* usa `-noaccurate_seek` + `-avoid_negative_ts make_zero`, alinhando áudio e vídeo no mesmo keyframe (evita o frame congelado no início observado em players simples como o Windows Media Player).

## Estrutura do Projeto

```
yt-clipper/
├── main.py                 # Ponto de entrada (aplica o perfil e abre a UI)
├── ui/
│   └── app_window.py       # Interface gráfica (CustomTkinter)
├── core/
│   ├── __init__.py         # Versão (__version__) e exportações públicas
│   ├── config.py           # Configuração tipada e imutável + perfis
│   ├── hardware.py         # Detecção de GPU/RAM/encoders (cacheada)
│   ├── bootstrap.py        # Aplica o perfil detectado na inicialização
│   ├── downloader.py       # Download via yt-dlp
│   ├── cutter.py           # Corte/conversão via ffmpeg (Strategy Pattern)
│   ├── updater.py          # Auto-update via instalador das Releases
│   ├── resources.py        # Caminhos de recursos empacotados
│   ├── processes.py        # Registro/cancelamento de subprocessos
│   └── logging_config.py   # Logging em arquivo
├── tests/                  # Testes automatizados (pytest + coverage)
├── .github/
│   ├── workflows/ci.yml    # Lint, formatação e testes
│   ├── workflows/release.yml # Build + Release em tags v*
│   ├── ISSUE_TEMPLATE/     # Templates de bug/feature
│   ├── dependabot.yml      # Atualizações de dependências
│   └── pull_request_template.md
├── assets/                 # ffmpeg/ffprobe (embutidos no instalador)
├── icons/
│   ├── app.ico             # Ícone do aplicativo e do instalador
│   └── app.png             # Master transparente usado para gerar o .ico
├── installer/
│   └── ytclipper.iss       # Script do Inno Setup (gera o Setup.exe)
├── tools/
│   └── make_icons.py       # Regenera os ícones com fundo transparente
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml          # Configuração de lint/format/testes/cobertura
├── .pre-commit-config.yaml
├── build.spec
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── LICENSE
└── README.md
```

## Licença

Licenciado sob a **MIT License**. Consulte o arquivo [`LICENSE`](LICENSE) para os termos completos.