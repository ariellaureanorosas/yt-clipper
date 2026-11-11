# 🎬 YouTube Clipper

Baixe vídeos do YouTube, corte trechos e converta para formato **vertical (9:16, para TikTok/Shorts/Reels)** ou **horizontal (16:9, para YouTube)** — tudo em um programa simples, com botões.

> Você não precisa saber programar. Siga o passo a passo abaixo.

---

## ✅ Como instalar (passo a passo)

### Antes de começar
- Você precisa de **Windows 10 ou 11**.
- Precisa ter **internet** (na primeira instalação).

### Passo 1 — Baixar o programa

1. Nesta página, clique no botão verde **`<> Code`**.
2. Clique em **`Download ZIP`**.
3. O arquivo **yt-clipper-main.zip** é baixado para a sua pasta "Downloads".

### Passo 2 — Extrair (descompactar)

1. Abra a sua pasta **Downloads**.
2. Clique com o **botão direito** no arquivo **yt-clipper-main.zip**.
3. Escolha **"Extrair tudo..."** e clique em **Extrair**.
4. Abra a pasta **yt-clipper-main** que foi criada. Ela contém o arquivo **`instalar.bat`**.

> ⚠️ **Importante:** copie ou extraia para uma pasta do seu computador (ex.: `Documentos`). **Não rode direto de dentro de um arquivo .zip aberto** — o programa não funcionaria.

### Passo 3 — Rodar o instalador

1. Na pasta **yt-clipper-main**, clique **duas vezes** em **`instalar.bat`**.
2. Vai abrir uma janela preta. **Aguarde** (a primeira vez leva alguns minutos, pois ele instala o que for preciso e prepara tudo).
3. O instalador instala o **Python automaticamente** se o computador ainda não tiver (baixa ~25 MB).
4. Ao final, a janela vai mostrar **"Pronto!"**.
5. Feche a janela clicando em qualquer tecla.

### Passo 4 — Abrir o programa

- Na sua **área de trabalho (Desktop)** apareceu o atalho **"YouTube Clipper"**.
- Clique duas vezes nele para abrir o programa. 🙂



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
> ⚠️ **Na primeira vez**, o programa pode precisar baixar o **ffmpeg** (~80 MB) e pedir que você aguarde a barra chegar a 100% antes de processar. Isso só acontece uma vez.

---

## ❓ Problemas comuns

### "Windows impediu a execução" (tela azul)
O Windows às vezes desconfia de programas recém-criados. Clique em **"Mais informações"** e depois em **"Executar assim mesmo"**.

### A janela do instalador fecha sozinha e não cria o atalho
Reinicie o computador e rode o **`instalar.bat`** novamente. Se o erro persistir na hora de instalar o Python, instale o Python manualmente de https://www.python.org/downloads/ (marcando a opção "Add python.exe to PATH") e rode o instalador de novo.

### "Não foi possível baixar o ffmpeg"
Isso acontece sem internet ou com rede bloqueada. Tente de novo mais tarde ou verifique sua conexão.

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
Feche e abra de novo. Se continuar, rode o **`instalar.bat`** novamente (ele conserta tudo).

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
| `YTCLIPPER_PROFILE` | auto | `high_end`, `mid_range`, `low_memory` ou `ci_cd` |
| `YTCLIPPER_LOW_MEMORY` | `false` | `true` força o modo de economia de memória |
| `YTCLIPPER_PREFER_HW` | `true` | `false` força encoding por CPU |
| `YTCLIPPER_DL_SOCKET_TIMEOUT` | `60` | Timeout de socket do download (segundos) |
| `YTCLIPPER_DL_RETRIES` | `5` | Número de tentativas de download |
| `YTCLIPPER_DL_CHUNK_SIZE` | `10485760` | Tamanho do chunk HTTP (bytes) |
| `YTCLIPPER_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Rodar em modo desenvolvimento

```bash
pip install -r requirements-dev.txt
python main.py
```

### Testes e qualidade de código

```bash
pytest                       # testes automatizados
ruff check .                 # lint (imports, nomes, erros)
black core ui tests main.py  # formatação
```

O repositório tem CI (GitHub Actions) que roda lint, formatação e testes a cada push/PR na branch `main`.

### Logs

Em caso de erro, o aplicativo grava um log de diagnóstico em:

```
%LOCALAPPDATA%\YouTubeClipper\logs\app.log
```

### Gerar o executável

```bash
pyinstaller build.spec
```

O `instalar.bat` faz isso automaticamente e ainda cria o atalho na área de trabalho.

### Correção (corte sem travamento no início)

O corte por *stream copy* usa `-noaccurate_seek` + `-avoid_negative_ts make_zero`, alinhando áudio e vídeo no mesmo keyframe (evita o frame congelado no início observado em players simples como o Windows Media Player).

## Estrutura do Projeto

```
yt-clipper/
├── main.py              # Ponto de entrada
├── ui/
│   └── app_window.py    # Interface gráfica
├── core/
│   ├── downloader.py    # Download via yt-dlp
│   ├── cutter.py        # Corte/conversão via ffmpeg
│   ├── processes.py     # Registro/cancelamento de subprocessos
│   └── logging_config.py # Logging em arquivo
├── tests/               # Testes automatizados (pytest)
├── assets/              # ffmpeg/ffprobe (baixados automaticamente na 1ª execução)
├── icons/
│   └── app.ico          # Ícone do aplicativo
├── instalar.bat         # Instalador para usuários (compila + atalho)
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml       # Configuração de lint/format/testes
├── build.spec
├── LICENSE
└── README.md
```

## Licença

Licenciado sob a **MIT License**. Consulte o arquivo [`LICENSE`](LICENSE) para os termos completos.