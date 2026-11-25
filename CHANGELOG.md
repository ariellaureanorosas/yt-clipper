# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-br/1.1.0/) e o
projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [1.3.1] - 2026-11-25

### Adicionado

- **Supervisor de atualização externo** (`tools/update_helper.py`, `build_helper.spec`): executável sem console instalado em `%LOCALAPPDATA%\YouTubeClipper\updater`, fora da pasta do aplicativo. Espera o app encerrar de verdade (por PID), faz backup por renomeação (sem copiar centenas de MB), executa o Setup com `/DIR` explícito, valida a versão instalada com `--version-file`, restaura o backup em caso de falha e reabre o app.
- **Estado persistente da atualização** (`core/update_state.py`): `pending.json`, `started.json` (handshake), `last-result.json` e `failed-version.json` com escrita atômica em `%LOCALAPPDATA%\YouTubeClipper\state`.
- **Supressão de versão que falhou**: uma versão com instalação malsucedida não é oferecida novamente por 24 h no check automático (verificação manual continua disponível).
- CLI `--version-file` no `main.py`: grava a versão embutida no exe e sai, usado pelo supervisor para validar a instalação.

### Alterado

- **Seleção exata do asset** (`core/updater.py:_find_installer_asset`): aceita apenas `YouTubeClipper-Setup-<versão>.exe`; nomes fora do padrão só são aceitos se a versão embutida corresponder exatamente à release. Corrige o bug da v1.2.1 que baixava qualquer `YouTubeClipper-*.exe`.
- **Download validado** (`core/updater.py:download_update`: confere tamanho vs. Content-Length, cabeçalho `MZ` e SHA-256 quando a release publica o checksum. Arquivos vazios/corrompidos são rejeitados antes de substituir o instalador final.
- **Aplicação via supervisor** (`core/updater.py:apply_update_and_restart`): grava o pedido, inicia o helper detached, aguarda o handshake antes de fechar a janela. Passa `/DIR=<pasta de instalação>` para não depender do registro.
- **Instalador** (`installer/ytclipper.iss`): supervisor instalado fora de `{app}` com `onlyifdoesntexist`; `[Run]` do silenciado gated por `YTCLIPPER_SKIP_RELAUNCH` para evitar dupla instância; `[UninstallDelete]` remove a pasta do supervisor.
- **Interface** (`ui/app_window.py`: lê `last-result.json` na abertura (mensagem única), mostra dialog de erro em falha, aguarda handshake antes de fechar, status "Instalando..." durante a aplicação.
- **CI** (`.github/workflows/release.yml`: passo de compilação do supervisor (`build_helper.spec`).

### Corrigido

- **Loop de atualização em falha**: antes, um instalador que saía com erro não era detectado e o app oferecia a mesma versão novamente. Agora o supervisor registra o resultado, restaura o backup e suprime a versão por 24 h.
- **Segundo atalho/instalação**: `/DIR` explícito impede que o Inno instale em um local diferente do registro.

## [1.3.0] - 2026-11-25

### Adicionado

- **Instalador (Setup.exe)** com Inno Setup: instala em
  `%LOCALAPPDATA%\Programs\YouTubeClipper` sem pedir senha de administrador,
  cria atalhos no Menu Iniciar/Área de Trabalho e desinstalador.
- **ffmpeg/ffprobe embutidos no instalador**: acabou o download de ~80 MB na
  primeira execução.
- Build em modo **onedir**: inicialização rápida, sem extrair os arquivos para
  `%TEMP%` a cada abertura.
- Botão **"Abrir pasta do app"** e exibição da versão/local de instalação na
  interface.

### Alterado

- **Atualização automática agora usa o instalador**: baixa o
  `YouTubeClipper-Setup-<versão>.exe`, confere o SHA-256 e o executa em modo
  silencioso. O aplicativo é fechado, atualizado e **reaberto automaticamente**,
  sem o script PowerShell oculto que falhava em silêncio.
- Ícone do aplicativo com **fundo transparente** (`icons/app.ico`), regerado em
  todos os tamanhos a partir do master `icons/app.png`.
- Ícone aplicado à janela, barra de título e **barra de tarefas**
  (`AppUserModelID`), inclusive nos atalhos criados pelo instalador.
- Metadados de versão no executável (aba **Detalhes** das Propriedades).

### Removido

- `instalar.bat` (substituído pelo instalador).
- Script PowerShell que trocava o `.exe` em execução.

## [1.2.0] - 2026-11-24

### Adicionado

- **Atualização automática** (`core/updater.py`): o executável consulta a
  última Release do GitHub, baixa o novo `.exe` em segundo plano, confere o
  SHA-256 e se substitui com o auxílio de um script PowerShell (o Windows não
  permite sobrescrever um `.exe` em execução). A interface pergunta antes de
  atualizar, mostra progresso e permite cancelar; falhas de rede não afetam o
  uso normal. Pode ser desligada com `YTCLIPPER_CHECK_UPDATES=false`.
- Botão **Verificar Atualizações** no diagnóstico do sistema.
- Configuração `UpdateConfig` (`enabled`, `check_on_start`, `timeout`) com
  suporte a variáveis de ambiente.

### Corrigido

- **Áudio atrasado no formato vertical**: ao converter para 1080×1920 o vídeo é
  re-encodado, mas o áudio AAC era apenas copiado (`-c:a copy`), mantendo os
  timestamps da origem e desalinhando o sincronismo A/V. Agora, sempre que o
  vídeo é re-encodado, o áudio também é re-encodado com
  `aresample=async=1:first_pts=0` e os streams são mapeados explicitamente com
  `-avoid_negative_ts make_zero`. O stream copy (horizontal) continua copiando o
  áudio, sem perda de qualidade nem custo extra.

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

Versão inicial.

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

[1.1.0]: https://github.com/ariellaureanorosas/yt-clipper/releases/tag/v1.1.0
