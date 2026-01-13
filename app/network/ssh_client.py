import socket
import paramiko
import logging
from typing import Tuple
from app.models.data_models import RadioResult
from app.models.exceptions import (
    DeviceOfflineError, 
    AuthenticationError, 
    SSHExecutionError
)

logger = logging.getLogger(__name__)

class SSHManager:
    def __init__(self, timeout: int = 12):
        self.timeout = timeout

    def is_port_open(self, host: str, port: int) -> bool:
        """Verifica se a porta TCP está aberta (substitui o ping de forma robusta)."""
        try:
            with socket.create_connection((host, port), timeout=self.timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def _get_ssh_client(self) -> paramiko.SSHClient:
        """Configura e retorna um cliente SSH com políticas de segurança estritas."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    def executar_comando(self, host: str, port: int, user: str, password: str, comando: str) -> str:
        """
        Executa comando via SSH com tratamento de exceções customizadas.
        Implementa proteção contra agentes de chaves e valida status de saída.
        """
        if not self.is_port_open(host, port):
            raise DeviceOfflineError(f"Host {host}:{port} inacessível.")

        client = self._get_ssh_client()
        try:
            # look_for_keys=False evita que o script tente usar suas chaves pessoais (ex: do GitHub)
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=self.timeout,
                banner_timeout=15,
                look_for_keys=False,
                allow_agent=False
            )

            stdin, stdout, stderr = client.exec_command(comando)
            
            # Garante que o comando terminou e captura o código de retorno (0 = Sucesso)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                erro_msg = stderr.read().decode('utf-8').strip()
                raise SSHExecutionError(f"Comando falhou (Code {exit_status}): {erro_msg}")

            return stdout.read().decode('utf-8').strip()

        except paramiko.AuthenticationException:
            raise AuthenticationError("Falha na autenticação (Usuário/Senha).")
        except paramiko.SSHException as e:
            raise SSHExecutionError(f"Erro de protocolo SSH: {str(e)}")
        finally:
            client.close()

    def contar_clientes(self, task) -> RadioResult:
        """Orquestra a consulta e converte exceções em um objeto RadioResult padronizado."""
        comando = "wstalist | grep -c '\"mac\"'"
        
        try:
            output = self.executar_comando(task.ip, task.port, task.username, task.password, comando)
            qtd = int(output) if output.isdigit() else 0
            
            return RadioResult(
                ip=task.ip,
                torre=task.torre,
                status="Online",
                clientes=qtd,
                observacao="Sucesso"
            )

        except DeviceOfflineError:
            return RadioResult(task.ip, task.torre, "Offline", 0, "Porta fechada/Timeout")
        except AuthenticationError:
            return RadioResult(task.ip, task.torre, "Erro Auth", 0, "Senha incorreta")
        except SSHExecutionError as e:
            return RadioResult(task.ip, task.torre, "Erro SSH", 0, str(e))
        except Exception as e:
            logger.error(f"Erro crítico em {task.ip}: {e}")
            return RadioResult(task.ip, task.torre, "Erro Crítico", 0, "Falha inesperada")