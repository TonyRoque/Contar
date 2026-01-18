import gc
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Dependências internas
from app.network.ssh_client import SSHClient, SSHCommandType
from app.utils.constants import NetworkConfig, StatusRadio, LogConfig
from app.models.exceptions import (
    DeviceOfflineError,
    AuthenticationError,
    SSHExecutionError
)

# Configuração de Log
logging.basicConfig(level=LogConfig.LOG_LEVEL, format=LogConfig.FORMAT, datefmt=LogConfig.DATE_FORMAT)
logger = logging.getLogger(__name__)

@dataclass
class ProcessamentoEngine:
    """
    Motor de orquestração com segurança de credenciais e alta performance.
    
    Características:
    - Validação antecipada de credenciais (eager validation)
    - Cache local com TTL para credenciais
    - Retry automático com backoff exponencial
    - Circuit breaker para proteção contra cascata de falhas
    - Timeout por tarefa para evitar travamentos
    """

    _config: Any = field(repr=False)  # Oculto em logs e repr()
    _timeout: int = field(default=NetworkConfig.SSH_TIMEOUT, repr=False)
    _max_workers: int = field(default=NetworkConfig.MAX_WORKERS, repr=False)
    _retry_attempts: int = field(default=NetworkConfig.RETRY_ATTEMPTS, repr=False)

    def __post_init__(self):
        """Validação imediata das credenciais no carregamento do objeto."""
        try:
            _ = self._get_credentials()
            logger.info("✅ Engine inicializado: Credenciais validadas.")
        except Exception as e:
            logger.critical(f"❌ Falha na validação do Engine: {e}")
            raise ValueError(f"Falha na validação do Engine: {e}") from e

    @lru_cache(maxsize=1)
    def _get_credentials(self) -> Tuple[str, str, int]:
        """
        Recupera credenciais com cache local (LRU).
        Retorna tupla imutável para evitar exposição global.
        
        Returns:
            Tupla (usuario, senha, porta)
            
        Raises:
            ValueError: Se credenciais não estão configuradas
        """
        user = self._config.get("SSH_USER")
        password = self._config.get("SSH_PASSWORD")
        port = int(self._config.get("SSH_PORT", 22))

        if not all([user, password]):
            raise ValueError("SSH_USER ou SSH_PASSWORD ausentes no arquivo .env")

        return user, password, port

    @retry(
        stop=stop_after_attempt(NetworkConfig.RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1,
            min=NetworkConfig.RETRY_BACKOFF_MIN,
            max=NetworkConfig.RETRY_BACKOFF_MAX
        ),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, DeviceOfflineError)),
        reraise=True
    )
    def _processar_com_retry(self, tarefa: Any) -> Dict[str, Any]:
        """
        Executa processamento de tarefa com retry automático.
        
        Args:
            tarefa: Objeto com atributos 'ip', 'nome', 'torre'
            
        Returns:
            Dicionário com resultado da operação
        """
        resultado = {
            "ip": tarefa.ip,
            "nome": getattr(tarefa, 'nome', 'N/A'),
            "torre": getattr(tarefa, 'torre', 'Desconhecida'),
            "status": StatusRadio.DESCONHECIDO.value,
            "clientes": 0,
            "hora": datetime.now().strftime("%H:%M:%S"),
            "erro": None
        }

        try:
            # Recupera credenciais apenas no escopo local
            user, password, port = self._get_credentials()

            # Conexão SSH com context manager (garante limpeza)
            with SSHClient(tarefa.ip, user, password, port, timeout=self._timeout) as client:
                # Executa comando seguro via allowlist
                output = client.execute_safe_command(SSHCommandType.WSTALIST, filters=["mac"])
                
                # Valida saída antes de casting
                if output and output.isdigit():
                    resultado["clientes"] = int(output)
                    resultado["status"] = StatusRadio.ONLINE.value
                else:
                    logger.warning(f"Output inesperado de {tarefa.ip}: {output[:50] if output else 'vazio'}")
                    resultado["status"] = StatusRadio.ERRO.value
                    resultado["erro"] = "Output inválido"

        except AuthenticationError as e:
            resultado["status"] = StatusRadio.ERRO_AUTH.value
            resultado["erro"] = "Credenciais inválidas"
            logger.warning(f"Auth falhou em {tarefa.ip}: {e}")
            
        except DeviceOfflineError as e:
            resultado["status"] = StatusRadio.OFFLINE.value
            resultado["erro"] = "Dispositivo inacessível"
            logger.warning(f"Dispositivo offline: {tarefa.ip}")
            
        except SSHExecutionError as e:
            resultado["status"] = StatusRadio.ERRO_SSH.value
            resultado["erro"] = str(e)[:100]
            logger.error(f"Erro SSH em {tarefa.ip}: {e}")
            
        except TimeoutError:
            resultado["status"] = StatusRadio.TIMEOUT.value
            resultado["erro"] = "Timeout na conexão"
            logger.warning(f"Timeout em {tarefa.ip}")
            
        except Exception as e:
            resultado["status"] = StatusRadio.ERRO.value
            resultado["erro"] = str(e)[:100]
            logger.error(f"Erro crítico em {tarefa.ip}: {e}", exc_info=True)

        return resultado

    def processar_unidade(self, tarefa: Any) -> Dict[str, Any]:
        """
        Processa uma tarefa com retry automático.
        
        Args:
            tarefa: Objeto com dados do rádio
            
        Returns:
            Dicionário com resultado
        """
        try:
            return self._processar_com_retry(tarefa)
        except Exception as e:
            # Última tentativa falhou após retries
            logger.error(f"Falha definitiva em {tarefa.ip}: {e}")
            return {
                "ip": tarefa.ip,
                "nome": getattr(tarefa, 'nome', 'N/A'),
                "torre": getattr(tarefa, 'torre', 'Desconhecida'),
                "status": StatusRadio.ERRO.value,
                "clientes": 0,
                "hora": datetime.now().strftime("%H:%M:%S"),
                "erro": "Falha após múltiplas tentativas"
            }

    def processar_em_lote(self, lista_tarefas: List[Any]) -> List[Dict[str, Any]]:
        """
        Processamento paralelo com timeout, circuit breaker e recuperação de erros.
        
        Args:
            lista_tarefas: Lista de tarefas a processar
            
        Returns:
            Lista de resultados (sucesso e falha)
        """
        resultados = []
        falhas_consecutivas = 0
        
        logger.info(f"Iniciando processamento de {len(lista_tarefas)} tarefas com {self._max_workers} workers")

        with ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="radio_"
        ) as executor:
            # Submete todas as tarefas
            futures = {
                executor.submit(self.processar_unidade, tarefa): tarefa
                for tarefa in lista_tarefas
            }

            # Processa resultados conforme completam
            for i, future in enumerate(as_completed(futures, timeout=self._timeout * 3)):
                tarefa = futures[future]

                try:
                    resultado = future.result(timeout=self._timeout)
                    resultados.append(resultado)
                    falhas_consecutivas = 0  # Reset na sucesso
                    
                    logger.debug(f"[{i+1}/{len(lista_tarefas)}] {tarefa.ip}: {resultado['status']}")

                except FuturesTimeoutError:
                    logger.error(f"Timeout na tarefa {tarefa.ip}")
                    resultados.append({
                        "ip": tarefa.ip,
                        "nome": getattr(tarefa, 'nome', 'N/A'),
                        "torre": getattr(tarefa, 'torre', 'Desconhecida'),
                        "status": StatusRadio.TIMEOUT.value,
                        "clientes": 0,
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "erro": "Timeout na execução"
                    })
                    falhas_consecutivas += 1

                except Exception as e:
                    logger.error(f"Erro em {tarefa.ip}: {e}")
                    resultados.append({
                        "ip": tarefa.ip,
                        "nome": getattr(tarefa, 'nome', 'N/A'),
                        "torre": getattr(tarefa, 'torre', 'Desconhecida'),
                        "status": StatusRadio.ERRO.value,
                        "clientes": 0,
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "erro": str(e)[:100]
                    })
                    falhas_consecutivas += 1

                # Circuit breaker: Interrompe se muitas falhas consecutivas
                if falhas_consecutivas >= NetworkConfig.CIRCUIT_BREAKER_THRESHOLD:
                    logger.critical(
                        f"🚨 Circuit breaker ativado! {falhas_consecutivas} falhas consecutivas. "
                        "Abortando processamento."
                    )
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

        logger.info(f"Processamento concluído: {len(resultados)}/{len(lista_tarefas)} tarefas completadas")
        return resultados

    def __del__(self):
        """Garante limpeza do cache de credenciais ao destruir o motor."""
        try:
            self._get_credentials.cache_clear()
            gc.collect()
        except Exception:
            pass  # Silenciosamente falha se já foi destruído