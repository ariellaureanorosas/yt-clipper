# Módulo core - lógica de download e corte

from core.config import (
    AppConfig,
    DownloadConfig,
    EncoderConfig,
    GPUVendor,
    HardwareProfile,
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

__all__ = [
    # config
    'get_config',
    'set_config',
    'reset_config',
    'AppConfig',
    'DownloadConfig',
    'EncoderConfig',
    'HardwareProfile',
    'GPUVendor',
    # hardware
    'get_cached_capabilities',
    'get_hardware_capabilities',
    'detect_hardware',
    'invalidate_hardware_cache',
    'HardwareCapabilities',
]
