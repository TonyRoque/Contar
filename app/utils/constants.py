"""
Configurações centralizadas para o projeto CONTAR.
Consolidada em um único arquivo para evitar inconsistências.
"""

from enum import Enum
from dataclasses import dataclass


class NetworkConfig:
    """Configurações de rede padronizadas."""
    
    # Timeouts SSH (em segundos)
    SSH_TIMEOUT = 12
    SSH_BANNER_TIMEOUT = 15
    SOCKET_TIMEOUT = 5
    
    # Pool de threads
    MAX_WORKERS = 10
    
    # Tarefas
    TASK_TIMEOUT = 30
    CIRCUIT_BREAKER_THRESHOLD = 5
    
    # Retry
    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF_MIN = 2  # segundos
    RETRY_BACKOFF_MAX = 10  # segundos


class RegioesDisponiveis(Enum):
    """Regiões conhecidas do projeto."""
    RJ = "RJ"
    SP = "SP"
    MG = "MG"
    BA = "BA"
    RS = "RS"


class StatusRadio(Enum):
    """Estados possíveis de um rádio."""
    ONLINE = "Online"
    OFFLINE = "Offline"
    ERRO_AUTH = "Erro Auth"
    ERRO_SSH = "Erro SSH"
    TIMEOUT = "Timeout"
    ERRO = "Erro"
    DESCONHECIDO = "Desconhecido"


class LogConfig:
    """Configurações de logging."""
    
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_LEVEL = "INFO"


@dataclass(frozen=True)
class Credenciais:
    """
    Credenciais SSH imutáveis.
    frozen=True evita modificações acidentais.
    """
    usuario: str
    senha: str
    
    def __repr__(self) -> str:
        """Nunca expõe credenciais em string representations."""
        return "Credenciais(usuario=*****, senha=****)"


# Mapa de prioridade para ordenação de status
STATUS_PRIORITY = {
    StatusRadio.ERRO.value: 0,
    StatusRadio.TIMEOUT.value: 1,
    StatusRadio.OFFLINE.value: 2,
    StatusRadio.ERRO_AUTH.value: 3,
    StatusRadio.ERRO_SSH.value: 4,
    StatusRadio.ONLINE.value: 5,
}
