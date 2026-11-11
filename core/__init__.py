# Módulo core - lógica de download e corte

from core.config import (
    get_config,
    set_config,
    reset_config,
    AppConfig,
    DownloadConfig,
    EncoderConfig,
    HardwareProfile,
    GPUVendor,
)
from core.hardware import (
    get_cached_capabilities,
    get_hardware_capabilities,
    detect_hardware,
    invalidate_hardware_cache,
    HardwareCapabilities,
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