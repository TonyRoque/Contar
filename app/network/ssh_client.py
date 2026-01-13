import socket
import paramiko
import logging
from typing import Tuple, Optional
from app.models.data_models import RadioResult

# Configuração de logging
logger = logging.getLogger(__name__)

class SSHManager:
    def __init__(self, timeout: int = 12):
        self.timeout = timeout

    def check_port(self, host: str, port: int) -> bool:
        """
        Verifica se a porta TCP está aberta (Substitui o Ping).
        Retorna True se conseguir conectar, False caso contrário.
        """
        try:
            # socket.AF_INET = IPv4, socket.SOCK_STREAM = TCP
            with socket.create_connection((host, port), timeout=self.timeout) as sock:
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def executar_comando(self, host: str, port: int, user: str, password: str, comando: str) -> Tuple[str, str]:
        """
        Conecta via SSH e executa um comando.
        Retorna uma tupla (output, erro).
        """
        # Primeiro, valida se o rádio está alcançável via porta TCP
        if not self.check_port(host, port):
            return "", "OFFLINE_PORT_CLOSED"

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Banner_timeout é crucial para rádios Ubiquiti sob carga
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=self.timeout,
                banner_timeout=15 
            )

            stdin, stdout, stderr = client.exec_command(comando)
            # Lê o resultado e limpa espaços vazios
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            return output, error

        except paramiko.AuthenticationException:
            return "", "AUTH_FAILED"
        except Exception as e:
            logger.error(f"Erro inesperado no rádio {host}: {str(e)}")
            return "", f"SSH_ERROR: {type(e).__name__}"
        finally:
            client.close()

    def contar_clientes(self, host: str, port: int, user: str, password: str) -> RadioResult:
        """
        Método de alto nível que orquestra a contagem e retorna um RadioResult.
        """
        # Comando otimizado que já faz a contagem no rádio (reduz tráfego de rede)
        comando = "wstalist | grep -c '\"mac\"'"
        
        output, erro = self.executar_comando(host, port, user, password, comando)
        
        # Lógica de decisão para o resultado
        if erro == "OFFLINE_PORT_CLOSED":
            return RadioResult(ip=host, status="Offline", clientes=0, observacao="Porta 22 fechada")
        elif erro == "AUTH_FAILED":
            return RadioResult(ip=host, status="Erro Auth", clientes=0, observacao="Credenciais incorretas")
        elif "SSH_ERROR" in erro:
            return RadioResult(ip=host, status="Erro SSH", clientes=0, observacao=erro)
        
        # Se chegou aqui, temos um output numérico
        qtd_clientes = int(output) if output.isdigit() else 0
        return RadioResult(
            ip=host, 
            status="Online", 
            clientes=qtd_clientes, 
            observacao="Sucesso"
        )
        