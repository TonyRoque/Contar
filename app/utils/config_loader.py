import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, dir_base: str):
        # Normaliza o caminho para evitar problemas com barras invertidas no Windows
        self.dir_base = os.path.abspath(dir_base)
        env_path = os.path.join(self.dir_base, '.env')
        
        if not os.path.exists(env_path):
            logger.warning(f"⚠️ Arquivo .env não encontrado em: {env_path}")
        else:
            load_dotenv(env_path, override=True) # Override garante que mude se trocar o arquivo
            logger.info(f"⚙️ Configurações carregadas da raiz: {self.dir_base}")

    def get_credentials(self, regiao: str) -> Tuple[str, str]:
        """
        Busca usuário e senha no .env baseado na região.
        """
        regiao_limpa = regiao.strip().upper()
        
        user = os.getenv(f"{regiao_limpa}_USER") or os.getenv("RADIO_USER")
        password = os.getenv(f"{regiao_limpa}_PASS") or os.getenv("RADIO_PASS")
        
        if not user or not password:
            msg = f"❌ Credenciais para '{regiao_limpa}' não encontradas no .env"
            logger.error(msg)
            raise ValueError(msg)
            
        return user, password

    def load_json_data(self, file_path: str) -> Dict[str, Any]:
        """
        Carrega e valida o arquivo JSON de rádios.
        """
        if not os.path.exists(file_path):
            logger.error(f"Arquivo não encontrado: {file_path}")
            raise FileNotFoundError(f"O arquivo não foi encontrado: {file_path}")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"📂 JSON carregado com sucesso: {os.path.basename(file_path)}")
                return data
        except json.JSONDecodeError as e:
            msg = f"Erro de sintaxe no JSON: {str(e)}"
            logger.error(msg)
            raise ValueError(msg)
        except Exception as e:
            msg = f"Erro ao ler JSON: {str(e)}"
            logger.error(msg)
            raise RuntimeError(msg)