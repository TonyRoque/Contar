from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class StatusRadioEnum(str, Enum):
    """Estados possíveis de um rádio."""
    ONLINE = "Online"
    OFFLINE = "Offline"
    ERRO_AUTH = "Erro Auth"
    ERRO_SSH = "Erro SSH"
    TIMEOUT = "Timeout"
    ERRO = "Erro"
    DESCONHECIDO = "Desconhecido"


@dataclass(frozen=True)
class RadioTask:
    """
    Dados de entrada para uma tarefa de consulta.
    
    Attributes:
        ip: Endereço IP do rádio
        torre: Nome/Identificador da torre
        username: Usuário SSH
        password: Senha SSH
        port: Porta SSH (padrão 22)
    """
    ip: str
    torre: str
    username: str
    password: str
    port: int = 22
    nome: Optional[str] = None


@dataclass
class RadioResult:
    """
    Estrutura padronizada para resultado de cada rádio.
    
    Attributes:
        ip: Endereço IP do rádio
        torre: Nome da torre
        status: Estado da conexão (enum)
        clientes: Número de clientes conectados
        observacao: Detalhes adicionais ou erro
    """
    ip: str
    torre: str
    status: str  # Usar StatusRadioEnum em novos códigos
    clientes: int = 0
    observacao: str = ""
    hora: Optional[str] = None

    def __post_init__(self):
        """Valida tipos de dados."""
        if not isinstance(self.ip, str):
            raise TypeError(f"ip deve ser str, recebido {type(self.ip)}")
        if not isinstance(self.clientes, int):
            raise TypeError(f"clientes deve ser int, recebido {type(self.clientes)}")
        if self.clientes < 0:
            raise ValueError(f"clientes não pode ser negativo: {self.clientes}")

    def __repr__(self) -> str:
        """Representação legível do resultado."""
        return (
            f"RadioResult(ip={self.ip!r}, status={self.status!r}, "
            f"clientes={self.clientes}, erro={self.observacao!r})"
        )