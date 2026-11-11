"""
Bootstrap da configuração da aplicação.

O perfil de hardware é detectado uma única vez e aplicado à configuração
global (download + encoder). Perfis definidos explicitamente por ambiente
(``YTCLIPPER_PROFILE``) têm prioridade e não são sobrescritos.
"""

from __future__ import annotations

from core.config import AppConfig, get_config, set_config
from core.hardware import get_cached_capabilities
from core.logging_config import get_logger

logger = get_logger(__name__)


def bootstrap_config(force_refresh: bool = False) -> AppConfig:
    """Aplica o perfil de hardware detectado à configuração global.

    É idempotente: se já houver um perfil definido (por ambiente ou por uma
    chamada anterior), nada muda. Use ``force_refresh=True`` para redetectar.

    Retorna a configuração efetiva em uso.
    """
    config = get_config()

    if config.hardware_profile is not None and not force_refresh:
        return config

    caps = get_cached_capabilities()
    config = config.with_profile(caps.profile)
    set_config(config)

    logger.info(
        'Perfil de hardware aplicado: %s (RAM %.1fGB, encoder hardware=%s, low_memory=%s)',
        caps.profile.value,
        caps.total_ram_gb,
        config.encoder.prefer_hardware,
        config.encoder.low_memory_mode,
    )
    return config
