import os
import sys
import logging
import ipaddress
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Importações internas
from app.utils.config_loader import ConfigLoader
from app.core.engine import ProcessamentoEngine
from app.utils.excel_generator import ExcelGenerator
from app.models.data_models import RadioTask

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================
os.makedirs('logs', exist_ok=True)
log_handler = RotatingFileHandler('logs/app.log', maxBytes=1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[log_handler, logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# MOTOR DE DESCOBERTA E NORMALIZAÇÃO (Sênior)
# =============================================================================

def extrair_tarefas_recursivo(dados, contexto_pai="Desconhecida"):
    """
    Percorre o JSON recursivamente em busca de listas de rádios.
    Transforma qualquer estrutura aninhada em uma lista plana para o motor.
    """
    tarefas_encontradas = []

    if isinstance(dados, dict):
        for chave, valor in dados.items():
            # Se encontrar uma lista, verifica se o primeiro item parece um rádio
            if isinstance(valor, list):
                for item in valor:
                    if isinstance(item, dict) and "ip" in item:
                        tarefas_encontradas.append({
                            "ip": item.get("ip"),
                            "torre": chave # O nome da chave atual vira a Torre
                        })
            else:
                # Continua mergulhando se for outro dicionário
                tarefas_encontradas.extend(extrair_tarefas_recursivo(valor, chave))
                
    return tarefas_encontradas

def validar_e_normalizar_ip(ip_str: str) -> str | None:
    if not ip_str or not isinstance(ip_str, str): return None
    ip_limpo = ip_str.strip().split(':')[0].replace('[', '').replace(']', '')
    try:
        return str(ipaddress.ip_address(ip_limpo))
    except ValueError:
        return None

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

# =============================================================================
# FLUXO PRINCIPAL
# =============================================================================

def iniciar():
    diretorio_raiz = os.getcwd()
    loader = ConfigLoader(diretorio_raiz)
    
    print("\n" + "="*60 + "\n🚀 SISTEMA CONTAR - CORE V0.8.5\n" + "="*60)

    caminho_json = selecionar_arquivo_json(os.path.join(diretorio_raiz, "data"))
    if not caminho_json:
        logger.error("Arquivo não selecionado ou inexistente.")
        return

    try:
        json_data = loader.load_json_data(caminho_json)
        
        # 1. Normalização dos Dados (Mergulho Inteligente)
        print("🔍 Analisando estrutura do arquivo...")
        dados_brutos = extrair_tarefas_recursivo(json_data)
        
        # 2. Carregamento de Credenciais (Baseado no Metadados do JSON)
        meta = json_data.get("METADADOS", {})
        regiao = meta.get("regiao", "PADRAO").upper()
        user, password = loader.get_credentials(regiao)
        
        if not user or not password:
            logger.error(f"Credenciais '{regiao}' ausentes no .env")
            return

        porta_json = meta.get("porta_padrao", 22)
        entrada_porta = input(f"\n👉 Porta SSH (Sugerida: {porta_json} | Enter para manter): ").strip()
        porta_final = int(entrada_porta) if entrada_porta.isdigit() else int(porta_json)

        # 3. Mapeamento para o Modelo Interno
        lista_tarefas = []
        for item in dados_brutos:
            ip_ok = validar_e_normalizar_ip(item["ip"])
            if ip_ok:
                lista_tarefas.append(RadioTask(
                    ip=ip_ok, torre=item["torre"],
                    username=user, password=password, port=porta_final
                ))

        total = len(lista_tarefas)
        if total == 0:
            logger.error("Nenhum rádio válido encontrado na estrutura.")
            return

        # 4. Execução do Motor
        def callback(n):
            p = (n / total) * 100
            print(f"   [Progresso: {n}/{total} ({p:.1f}%)]", end='\r', flush=True)

        engine = ProcessamentoEngine(max_workers=25)
        resultados = engine.processar_radios(lista_tarefas, callback_progresso=callback)
        print(" " * 60, end='\r')

        # 5. Relatório
        nome_excel = f"Relatorio_{regiao}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        ExcelGenerator.gerar_relatorio(resultados, nome_excel)
        
        on = sum(1 for r in resultados if r.status == "Online")
        print(f"\n✅ CONCLUÍDO! Online: {on}/{total} | Relatório: {nome_excel}\n")

    except Exception as e:
        logger.critical(f"Erro fatal: {e}", exc_info=True)

if __name__ == "__main__":
    iniciar()