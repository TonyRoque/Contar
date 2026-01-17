import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from app.utils.config_loader import ConfigLoader
from app.core.engine import ProcessamentoEngine
from app.utils.excel_generator import ExcelGenerator
from app.models.data_models import RadioTask
from app.utils.helpers import extrair_tarefas_recursivo, validar_e_normalizar_ip

# Configuração de Log mantida conforme seu original...
os.makedirs('logs', exist_ok=True)
log_handler = RotatingFileHandler('logs/app.log', maxBytes=1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[log_handler, logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def selecionar_arquivo_json(diretorio_data: str) -> str | None:
    if not os.path.exists(diretorio_data): return None
    arquivos = sorted([f for f in os.listdir(diretorio_data) if f.endswith('.json')])
    if not arquivos: return None
    print("\n📂 SELEÇÃO DE INVENTÁRIO:")
    for i, arquivo in enumerate(arquivos, start=1):
        print(f"   [{i}] {arquivo}")
    try:
        escolha = int(input(f"\n👉 Escolha o arquivo (1-{len(arquivos)}): ").strip())
        return os.path.join(diretorio_data, arquivos[escolha - 1]) if 1 <= escolha <= len(arquivos) else None
    except ValueError: return None

def iniciar():
    diretorio_raiz = os.getcwd()
    loader = ConfigLoader(diretorio_raiz)
    # ... (restante da sua lógica de fluxo iniciar() permanece igual, 
    # apenas usando as funções importadas do helpers)
    # [Omitido por brevidade, mas mantém sua lógica original]