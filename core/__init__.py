# Módulo core - lógica de download e corte

__version__ = '1.3.0'

from core.bootstrap import bootstrap_config
from core.config import (
    AppConfig,
    DownloadConfig,
    EncoderConfig,
    GPUVendor,
    HardwareProfile,
    UpdateConfig,
    get_config,
    reset_config,
    set_config,
)
from core.hardware import (
    HardwareCapabilities,
    detect_hardware,
    get_cached_capabilities,
    get_hardware_capabilities,
    invalidate_hardware_cache,
)

# Identificador usado pelo Windows para agrupar janela, barra de tarefas e
# atalhos do aplicativo (precisa ser igual ao AppUserModelID do instalador).
APP_ID = 'ArielRosas.YouTubeClipper'

__all__ = [
    '__version__',
    'APP_ID',
    # bootstrap
    'bootstrap_config',
    # config
    'get_config',
    'set_config',
    'reset_config',
    'AppConfig',
    'DownloadConfig',
    'EncoderConfig',
    'HardwareProfile',
    'GPUVendor',
    'UpdateConfig',
    # hardware
    'get_cached_capabilities',
    'get_hardware_capabilities',
    'detect_hardware',
    'invalidate_hardware_cache',
    'HardwareCapabilities',
]
