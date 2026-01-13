import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Tuple

# Configuração básica de log para este módulo
logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, dir_base: str):
        self.dir_base = dir_base
        env_path = os.path.join(self.dir_base, '.env')
        
        # v0.2: Verifica se o .env existe antes de carregar
        if not os.path.exists(env_path):
            logger.warning(f"Arquivo .env não encontrado em: {env_path}")
        
        load_dotenv(env_path)

    def get_credentials(self, regiao: str) -> Tuple[str, str]:
        """
        Busca usuário e senha no .env baseado na região.
        Trata espaços e diferenças entre maiúsculas/minúsculas.
        """
        # Limpeza da string para evitar erros de digitação
        regiao_limpa = regiao.strip().upper()
        
        user = os.getenv(f"{regiao_limpa}_USER") or os.getenv("RADIO_USER")
        password = os.getenv(f"{regiao_limpa}_PASS") or os.getenv("RADIO_PASS")
        
        if not user or not password:
            msg = f"Credenciais para a região '{regiao_limpa}' não encontradas no .env"
            logger.error(msg)
            raise ValueError(msg)
            
        return user, password

    def load_json_data(self, file_path: str) -> Dict[str, Any]:
        """
        Carrega e valida o arquivo JSON de rádios com tratamento de erro robusto.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"O arquivo não foi encontrado: {file_path}")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            msg = f"Erro de sintaxe no JSON: {str(e)}"
            logger.error(msg)
            raise ValueError(msg)
        except PermissionError:
            msg = "Sem permissão para ler o arquivo selecionado."
            logger.error(msg)
            raise PermissionError(msg)
        except Exception as e:
            msg = f"Erro inesperado ao ler JSON: {type(e).__name__}"
            logger.error(msg)
            raise RuntimeError(msg)