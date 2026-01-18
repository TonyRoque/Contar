import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Tuple
from pathlib import Path

from app.utils.constants import RegioesDisponiveis, Credenciais

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Carregador de configurações com validação expl\u00edcita e tratamento de erros.
    
    Recursos:
    - Carrega vari\u00e1veis do arquivo .env
    - Valida credenciais por regi\u00e3o (sem fallback silencioso)
    - Carrega e valida arquivos JSON
    - Logging estruturado de opera\u00e7\u00f5es
    """

    def __init__(self, dir_base: str):
        """
        Inicializa o carregador de configura\u00e7\u00f5es.
        
        Args:
            dir_base: Diret\u00f3rio raiz onde est\u00e1 o arquivo .env
        """
        self.dir_base = Path(dir_base).resolve()
        env_path = self.dir_base / '.env'
        
        if not env_path.exists():
            logger.warning(f"\u26a0\ufe0f Arquivo .env n\u00e3o encontrado em: {env_path}")
            logger.warning("Valores padr\u00e3o do sistema ser\u00e3o usados (variáveis de ambiente)")
        else:
            load_dotenv(env_path, override=True)
            logger.info(f"\u2705 Configura\u00e7\u00f5es carregadas de: {env_path}")

    def get_credentials(self, regiao: str) -> Credenciais:
        """
        Busca credenciais por regi\u00e3o com valida\u00e7\u00e3o expl\u00edcita.
        
        Args:
            regiao: Nome da regi\u00e3o (ex: 'RJ', 'SP')
            
        Returns:
            Objeto Credenciais (imut\u00e1vel)
            
        Raises:
            ValueError: Se regi\u00e3o desconhecida ou credenciais incompletas
        """
        regiao_limpa = regiao.strip().upper()
        
        # Valida regi\u00e3o contra Enum
        try:
            RegioesDisponiveis[regiao_limpa]
        except KeyError:
            regioes_validas = ', '.join(r.value for r in RegioesDisponiveis)
            raise ValueError(
                f"\u274c Regi\u00e3o desconhecida: {regiao_limpa!r}\n"
                f"Regi\u00f5es v\u00e1lidas: {regioes_validas}"
            )
        
        # Busca vari\u00e1veis espec\u00edficas da regi\u00e3o
        user_key = f"{regiao_limpa}_USER"
        pass_key = f"{regiao_limpa}_PASS"
        
        user = os.getenv(user_key)
        password = os.getenv(pass_key)
        
        # Valida se est\u00e3o completas
        if not user or not password:
            missing = []
            if not user:
                missing.append(user_key)
            if not password:
                missing.append(pass_key)
            
            raise ValueError(
                f"\u274c Credenciais incompletas para {regiao_limpa}\n"
                f"Vari\u00e1veis faltando: {', '.join(missing)}\n"
                f"Configure no arquivo .env e reinicie a aplica\u00e7\u00e3o."
            )
        
        logger.info(f"\u2705 Credenciais carregadas para regi\u00e3o: {regiao_limpa}")
        return Credenciais(usuario=user, senha=password)

    def get(self, chave: str, padrao: Any = None) -> Any:
        """
        Recupera vari\u00e1vel de ambiente com valor padr\u00e3o opcional.
        
        Args:
            chave: Nome da vari\u00e1vel
            padrao: Valor padr\u00e3o se n\u00e3o encontrada
            
        Returns:
            Valor da vari\u00e1vel ou padr\u00e3o
        """
        return os.getenv(chave, padrao)

    def load_json_data(self, file_path: str) -> Dict[str, Any]:
        """
        Carrega e valida arquivo JSON de invent\u00e1rio.
        
        Args:
            file_path: Caminho absoluto do arquivo JSON
            
        Returns:
            Dicion\u00e1rio com dados do JSON
            
        Raises:
            FileNotFoundError: Se arquivo n\u00e3o existe
            ValueError: Se JSON est\u00e1 malformado
            RuntimeError: Para erros inesperados
        """
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            logger.error(f"Arquivo n\u00e3o encontrado: {file_path}")
            raise FileNotFoundError(f"Arquivo n\u00e3o encontrado: {file_path}")
        
        if file_path.suffix.lower() != '.json':
            logger.warning(f"Arquivo pode n\u00e3o ser JSON: {file_path.suffix}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"\u2705 JSON carregado com sucesso: {file_path.name}")
                return data
                
        except json.JSONDecodeError as e:
            logger.error(f"Erro de sintaxe no JSON: {e.msg} (linha {e.lineno})")
            raise ValueError(f"JSON malformado: {e.msg} na linha {e.lineno}") from e
            
        except UnicodeDecodeError as e:
            logger.error(f"Erro de encoding no arquivo: {e}")
            raise ValueError(f"Erro de encoding: o arquivo n\u00e3o \u00e9 UTF-8 v\u00e1lido") from e
            
        except Exception as e:
            logger.error(f"Erro ao ler arquivo JSON: {e}", exc_info=True)
            raise RuntimeError(f"Erro ao ler arquivo JSON: {e}") from e

    def load_csv_data(self, file_path: str) -> list:
        """
        Carrega dados de um arquivo CSV (para futura expans\u00e3o).
        
        Args:
            file_path: Caminho do arquivo CSV
            
        Returns:
            Lista de dicion\u00e1rios com dados do CSV
        """
        import csv
        
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo n\u00e3o encontrado: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
                logger.info(f"\u2705 CSV carregado: {len(data)} linhas")
                return data
                
        except Exception as e:
            logger.error(f"Erro ao ler CSV: {e}")
            raise RuntimeError(f"Erro ao ler CSV: {e}") from e