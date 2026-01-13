from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)  # frozen=True torna o objeto imutável, evitando alterações acidentais
class RadioTask:
    """Dados de entrada para uma tarefa de consulta."""
    ip: str
    torre: str
    username: str
    password: str
    port: int = 22

@dataclass
class RadioResult:
    """Estrutura padronizada para o resultado de cada rádio."""
    ip: str
    torre: str
    status: str      # 'Online', 'Offline', 'Erro Auth', 'Erro SSH'
    clientes: int = 0
    observacao: str = ""