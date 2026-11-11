# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-br/1.1.0/) e o
projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Planejado

- Testes automatizados para a interface (Tkinter) com `pytest` + mocks de janela.
- Assinatura digital do executável para reduzir avisos do Windows SmartScreen.

## [1.1.0] - 2026-11-11

### Adicionado

- **Perfil de hardware aplicado automaticamente na inicialização**
  (`core/bootstrap.py`): RAM, GPU e encoders disponíveis definem download,
  threads e modo de economia de memória. O perfil pode ser sobrescrito por
  `YTCLIPPER_PROFILE`.
- **Stream copy inteligente** (`StreamCopyStrategy`): cortes que mantêm a
  resolução e já são H.264 não passam por re-encode, ficando quase
  instantâneos. O modo usa `-noaccurate_seek` e `-avoid_negative_ts make_zero`
  para evitar travamento no primeiro frame.
- **Diagnóstico do sistema** passa a exibir a versão do app e o estado do modo
  de baixa memória.
- Cobertura de testes com `pytest-cov` (mínimo de 55% para `core`) e novos
  testes para configuração, hardware, bootstrap, processos, cutter e downloader.
- `pre-commit`, `.editorconfig` e `.gitattributes` para padronizar o código e
  os finais de linha.
- Documentação de contribuição, código de conduta, política de segurança e
  templates de issue/PR.
- Workflow de release que compila o executável e publica os artefatos em tags
  `v*`.

### Corrigido

- **Configuração imutável**: `AppConfig.with_profile()` e o toggle "Forçar CPU"
  agora usam `dataclasses.replace`, preservando opções personalizadas (log,
  timeouts, overrides) em vez de recriar a config com valores padrão.
- **`YTCLIPPER_PROFILE` inválido** não derruba mais a aplicação; o valor é
  ignorado.
- **`YTCLIPPER_PREFER_HW`** passa a ter prioridade sobre o preset do perfil.
- **Cache de hardware**: `invalidate_hardware_cache()` também limpa as
  capacidades em memória, garantindo redetecção real.
- **Stream copy não depende mais de `prefer_hardware`**, e a estratégia usada
  no caminho de cópia passou a ser válida (antes eram passados argumentos
  incompatíveis a `CPUStrategy`).

### Alterado

- Versão do aplicativo centralizada em `core.__version__`.
- `requirements-dev.txt` inclui `pytest-cov` e `pre-commit`.

## [1.0.0] - 2026-10-01

### Adicionado

- Download de vídeos do YouTube com `yt-dlp`, incluindo Shorts, lives e links
  `youtu.be`.
- Corte e conversão para **horizontal (1920×1080)** e **vertical (1080×1920)**
  com `ffmpeg`.
- Seleção de trecho por sliders ou digitação de tempo.
- Detecção de GPU (NVENC, QuickSync, VAAPI, VideoToolbox) com fallback para CPU.
- Modo de economia de memória para PCs com pouca RAM.
- Instalador (`instalar.bat`) que instala Python, dependências e cria atalho.
- Cancelamento seguro de subprocessos e limpeza de arquivos temporários.
- Logs em `%LOCALAPPDATA%\YouTubeClipper\logs\app.log`.

[1.1.0]: https://github.com/ariellaureanorosas/yt-clipper/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ariellaureanorosas/yt-clipper/releases/tag/v1.0.0
