# 🎬 YouTube Clipper

**Baixe vídeos do YouTube, corte trechos e converta para formato **vertical (9:16, para TikTok/Shorts/Reels)** ou **horizontal (16:9, para YouTube)** — tudo em um programa simples, com botões.

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

### Passo 3 — Instalar o Python (só na primeira vez)

O programa precisa do **Python** instalado no computador:

1. Acesse: **https://www.python.org/downloads/**
2. Clique no botão amarelo **"Download Python 3.x"**.
3. Abra o arquivo baixado.
4. **MUITO IMPORTANTE:** na primeira tela, **marque a caixinha** `Add python.exe to PATH` (no rodapé).
5. Clique em **Install Now** e aguarde terminar.
6. Ao final, clique em **Close**.

### Passo 4 — Rodar o instalador

1. Na pasta **yt-clipper-main**, clique **duas vezes** em **`instalar.bat`**.
2. Vai abrir uma janela preta. **Aguarde** (a primeira vez leva alguns minutos, pois ele baixa e prepara tudo).
3. Ao final, a janela vai mostrar **"Pronto!"**.
4. Feche a janela clicando em qualquer tecla.

### Passo 5 — Abrir o programa

- Na sua **área de trabalho (Desktop)** apareceu o atalho **"YouTube Clipper"**.
- Clique duas vezes nele para abrir o programa. 🙂



---

## 🎮 Como usar o programa

1. **Cole o link do vídeo** do YouTube no campo lá de cima (aquele que começa com `https://www.youtube.com/watch?v=...`).
2. Clique em **Carregar**. O programa mostra o título do vídeo, a duração e a miniatura.
3. **Escolha o formato:**
   - **Horizontal (1920×1080)** — formato normal, para YouTube.
   - **Vertical (1080×1920)** — formato de celular, para Shorts/TikTok/Reels.
4. **Escolha o trecho** (início e fim) usando as barrinhas deslizantes ou digitando o tempo (`00:01:30`).
5. Clique em **📁 Selecionar pasta** para escolher onde salvar o vídeo.
6. Clique no botão **Processar**.
7. Espere a barra de progresso chegar a 100%. Pronto! Seu vídeo recortado está na pasta escolhida. ✅

> 💡 Dica: quanto menor o trecho, mais rápido fica pronto. Cortes que não mudam o formato são quase instantâneos.

---

## ❓ Problemas comuns

### "Windows impediu a execução" (tela azul)
O Windows às vezes desconfia de programas recém-criados. Clique em **"Mais informações"** e depois em **"Executar assim mesmo"**.

### A janela do instalador fecha sozinha e não cria o atalho
Verifique se o **Python foi instalado com a caixinha "Add python.exe to PATH" marcada** (Passo 3). Se não marcou, instale de novo marcando a opção.

### "Não foi possível baixar o ffmpeg"
Isso acontece sem internet ou com rede bloqueada. Tente de novo mais tarde ou verifique sua conexão.

### O programa não abre
Feche e abra de novo. Se continuar, rode o **`instalar.bat`** novamente (ele conserta tudo).

---

## 💻 Informações para desenvolvedores

**Tecnologias:** Python + CustomTkinter (interface), yt-dlp (download), ffmpeg (corte/conversão).

### Rodar em modo desenvolvimento

```bash
pip install -r requirements.txt
python main.py
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
│   └── cutter.py        # Corte/conversão via ffmpeg
├── assets/              # ffmpeg/ffprobe (embutidos no .exe)
├── icons/
│   └── app.ico          # Ícone do aplicativo
├── instalar.bat         # Instalador para usuários (compila + atalho)
├── requirements.txt
├── build.spec
└── README.md
```

## Licença

Uso pessoal / interno.