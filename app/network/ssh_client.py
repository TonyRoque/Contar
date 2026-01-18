import logging
import re
import socket
import hashlib
from enum import Enum
from typing import Optional, List
from pathlib import Path
import paramiko

from app.utils.constants import NetworkConfig
from app.models.exceptions import (
    DeviceOfflineError,
    AuthenticationError,
    SSHExecutionError
)

# Configuração de Logs
logger = logging.getLogger(__name__)


class SSHCommandType(Enum):
    """Define os comandos permitidos (Allowlist) para evitar injeção de comando."""
    WSTALIST = "wstalist"
    SYSTEM_STATUS = "mca-status"
    UPTIME = "uptime"


class SSHClient:
    """
    Cliente SSH seguro com:
    - Proteção contra injeção de comandos (Allowlist)
    - Context Manager para limpeza garantida
    - Validação de entrada robusta
    - Timeout por operação
    
    Uso:
        with SSHClient(host, user, password) as client:
            output = client.execute_safe_command(SSHCommandType.WSTALIST)
    """

    KNOWN_HOSTS_FILE = Path.home() / ".ssh" / "known_hosts"
    FINGERPRINT_CACHE = {}  # Cache local de fingerprints

    def __init__(self, host: str, user: str, password: str, port: int = 22, timeout: int = NetworkConfig.SSH_TIMEOUT):
        """
        Inicializa o cliente SSH.
        
        Args:
            host: Hostname ou IP do servidor
            user: Username para autenticação
            password: Password para autenticação
            port: Porta SSH (default 22)
            timeout: Timeout em segundos
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.timeout = timeout
        self.client = None
        self._connected = False

    def __enter__(self):
        """Implementa o Context Manager: 'with' statement."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Garante fechamento da conexão ao sair do bloco 'with'."""
        self.close()
        return False  # Não suprime exceções

    def connect(self) -> None:
        """
        Estabelece conexão SSH com proteções de segurança.
        
        Raises:
            DeviceOfflineError: Se o host não está acessível
            AuthenticationError: Se credenciais são inválidas
            SSHExecutionError: Para outros erros SSH
        """
        try:
            # Verifica se porta está aberta
            if not self._is_port_open():
                raise DeviceOfflineError(f"Host {self.host}:{self.port} inacessível")

            self.client = paramiko.SSHClient()
            
            # SEGURANÇA: Valida fingerprint do host
            self._configure_host_key_policy()
            
            logger.debug(f"Conectando em {self.host}:{self.port}...")
            
            self.client.connect(
                hostname=self.host,
                username=self.user,
                password=self.password,
                port=self.port,
                timeout=self.timeout,
                banner_timeout=NetworkConfig.SSH_BANNER_TIMEOUT,
                look_for_keys=False,  # Não usa chaves locais
                allow_agent=False      # Não usa ssh-agent
            )
            
            self._connected = True
            logger.debug(f"✅ Conectado em {self.host}")

        except socket.timeout:
            raise DeviceOfflineError(f"Timeout ao conectar em {self.host}:{self.port}")
        except (socket.gaierror, ConnectionRefusedError, OSError) as e:
            raise DeviceOfflineError(f"Host {self.host} inacessível: {e}")
        except paramiko.AuthenticationException as e:
            raise AuthenticationError(f"Falha na autenticação em {self.host}: {e}")
        except paramiko.SSHException as e:
            raise SSHExecutionError(f"Erro SSH em {self.host}: {e}")
        except Exception as e:
            raise SSHExecutionError(f"Erro desconhecido ao conectar em {self.host}: {e}")

    def _is_port_open(self) -> bool:
        """Verifica se a porta TCP está aberta (sem usar ping)."""
        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=NetworkConfig.SOCKET_TIMEOUT
            ):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def _configure_host_key_policy(self) -> None:
        """
        Configura a política de validação de chaves do host.
        
        Em desenvolvimento: Aceita chaves desconhecidas (AutoAddPolicy)
        Em produção: Deve usar RejectPolicy + load_system_host_keys()
        """
        if self.KNOWN_HOSTS_FILE.exists():
            # Produção: Usa known_hosts
            self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            self.client.load_system_host_keys()
            logger.debug(f"Host key policy: RejectPolicy (usando {self.KNOWN_HOSTS_FILE})")
        else:
            # Desenvolvimento: Aceita chaves desconhecidas com logging
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            logger.warning(
                f"⚠️ {self.KNOWN_HOSTS_FILE} não existe. "
                "Usando AutoAddPolicy (inseguro para produção)."
            )

    def _build_safe_command(
        self,
        cmd_type: SSHCommandType,
        filters: Optional[List[str]] = None
    ) -> str:
        """
        Constrói comando SSH de forma segura usando Allowlist.
        
        Args:
            cmd_type: Tipo de comando pré-validado (Enum)
            filters: Filtros adicionais (são validados contra regex)
            
        Returns:
            Comando seguro pronto para execução
            
        Raises:
            ValueError: Se um filtro contém caracteres maliciosos
        """
        base_cmd = cmd_type.value

        if not filters:
            return base_cmd

        validated_filters = []
        
        for f in filters:
            # Regex restrito: apenas alphanumeros, hifen e underscore
            if not re.match(r"^[a-zA-Z0-9_\-]+$", f):
                raise ValueError(f"Filtro malicioso detectado: {f!r}")
            
            # Constrói filtro seguro (usando grep para contagem)
            validated_filters.append(f'grep -c \'"{f}\'')

        if validated_filters:
            return f"{base_cmd} | {' | '.join(validated_filters)}"
        
        return base_cmd

    def execute_safe_command(
        self,
        cmd_type: SSHCommandType,
        filters: Optional[List[str]] = None
    ) -> str:
        """
        Executa um comando pré-validado (allowlist).
        
        Args:
            cmd_type: Tipo de comando da allowlist (Enum)
            filters: Filtros adicionais (validados automaticamente)
            
        Returns:
            Output do comando (string)
            
        Raises:
            ConnectionError: Se não conectado
            SSHExecutionError: Se o comando falha
        """
        if not self._connected or not self.client:
            raise ConnectionError("Cliente SSH não está conectado. Use 'with' statement.")

        try:
            comando = self._build_safe_command(cmd_type, filters)
            logger.debug(f"Executando em {self.host}: {comando}")
            
            stdin, stdout, stderr = self.client.exec_command(
                comando,
                timeout=self.timeout
            )
            
            # Aguarda conclusão e captura código de saída
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()

            if exit_status != 0:
                erro_msg = error or f"Comando falhou com código {exit_status}"
                logger.warning(f"Erro em {self.host}: {erro_msg}")
                raise SSHExecutionError(f"Comando falhou: {erro_msg}")

            logger.debug(f"✅ Comando executado em {self.host}: {output[:50]}")
            return output

        except SSHExecutionError:
            raise
        except paramiko.SSHException as e:
            raise SSHExecutionError(f"Erro de protocolo SSH em {self.host}: {e}")
        except Exception as e:
            raise SSHExecutionError(f"Erro ao executar comando em {self.host}: {e}")

    def close(self) -> None:
        """Encerra a sessão SSH de forma limpa."""
        if self.client:
            try:
                self.client.close()
                self._connected = False
                logger.debug(f"Conexão fechada: {self.host}")
            except Exception as e:
                logger.error(f"Erro ao fechar conexão em {self.host}: {e}")
            finally:
                self.client = None