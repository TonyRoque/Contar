import gc
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Dependência interna para execução SSH
from app.network.ssh_client import SSHClient

# Configuração de Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessamentoEngine:
    """
    Motor de orquestração com segurança de credenciais e alta performance.
    Utiliza validação antecipada e limpeza de memória para mitigar riscos de segurança.
    """

    _config: Any = field(repr=False)  # Oculto em logs e repr()
    _timeout: int = field(default=12, repr=False)

    def __post_init__(self):
        """Validação imediata das credenciais no carregamento do objeto."""
        try:
            # Verifica se as credenciais existem no config_loader
            _ = self._get_credentials()
            logger.info("Engine inicializado: Segurança de credenciais validada.")
        except Exception as e:
            raise ValueError(f"Falha na validação do Engine: {e}") from e

    @lru_cache(maxsize=1)
    def _get_credentials(self) -> Tuple[str, str, int]:
        """
        Recupera credenciais com cache local.
        Retorna tupla imutável para evitar exposição global em atributos de classe.
        """
        user = self._config.get("SSH_USER")
        password = self._config.get("SSH_PASSWORD")
        port = int(self._config.get("SSH_PORT", 22))

        if not all([user, password]):
            raise ValueError("SSH_USER ou SSH_PASSWORD ausentes no arquivo .env")

        return user, password, port

    def processar_unidade(self, tarefa: Any) -> Dict[str, Any]:
        """
        Executa a conexão e extração de dados de um único rádio.
        Implementa retorno padronizado para o Dashboard do Streamlit.
        """
        resultado = {
            "ip": tarefa.ip,
            "nome": getattr(tarefa, 'nome', 'N/A'),
            "status": "Iniciando...",
            "clientes": 0,
            "hora": datetime.now().strftime("%H:%M:%S"),
            "erro": None
        }

        try:
            # Recupera credenciais apenas no escopo local da função
            user, password, port = self._get_credentials()

            # Conexão SSH (utilizando o seu SSHClient)
            with SSHClient(tarefa.ip, user, password, port, timeout=self._timeout) as client:
                # Comando padrão Ubiquiti para contagem de MACs associados
                output = client.execute("wstalist | grep -c mac")
                
                resultado["clientes"] = int(output.strip()) if output.strip().isdigit() else 0
                resultado["status"] = "Online"

        except Exception as e:
            resultado["status"] = "Falha"
            resultado["erro"] = str(e)
            logger.error(f"Erro em {tarefa.ip}: {e}")

        return resultado

    def processar_em_lote(self, lista_tarefas: List[Any], max_workers: int = 10) -> List[Dict[str, Any]]:
        """
        Processamento paralelo utilizando ThreadPoolExecutor.
        Ideal para varredura de ranges de IP (Pool).
        """
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            resultados = list(executor.map(self.processar_unidade, lista_tarefas))
        return resultados

    def __del__(self):
        """Garante a limpeza do cache de credenciais e coleta de lixo ao destruir o motor."""
        self._get_credentials.cache_clear()
        gc.collect()