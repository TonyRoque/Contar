import os
import sys
import json
import logging
import ipaddress
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Importações internas do seu projeto
from app.utils.config_loader import ConfigLoader
from app.core.engine import ProcessamentoEngine
from app.utils.excel_generator import ExcelGenerator
from app.models.data_models import RadioTask

# =============================================================================
# CONFIGURAÇÃO DE LOGGING (Padrão Sênior)
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
# FUNÇÕES AUXILIARES DE VALIDAÇÃO
# =============================================================================

def validar_e_normalizar_ip(ip_str: str) -> str | None:
    """Limpa, valida e normaliza endereços IPv4 ou IPv6."""
    if not ip_str or not isinstance(ip_str, str):
        return None
    
    ip_limpo = ip_str.strip()
    # Tratamento para IPv6 [::1]:porta ou IPv4 1.1.1.1:22
    if '[' in ip_limpo and ']' in ip_limpo:
        ip_limpo = ip_limpo.split(']')[0].replace('[', '')
    elif ':' in ip_limpo and ip_limpo.count(':') == 1:
        ip_limpo = ip_limpo.split(':')[0]
    
    try:
        return str(ipaddress.ip_address(ip_limpo))
    except ValueError:
        return None

def selecionar_arquivo_json(diretorio_data: str) -> str | None:
    """Lista arquivos .json e gerencia a escolha do usuário."""
    if not os.path.exists(diretorio_data):
        logger.error(f"Pasta de dados não encontrada: {diretorio_data}")
        return None

    arquivos = sorted([f for f in os.listdir(diretorio_data) if f.endswith('.json')])
    
    if not arquivos:
        logger.error(f"Nenhum arquivo .json encontrado em: {diretorio_data}")
        return None

    print("\n📂 SELEÇÃO DE INVENTÁRIO:")
    for i, arquivo in enumerate(arquivos, start=1):
        print(f"   [{i}] {arquivo}")
    
    try:
        escolha = int(input(f"\n👉 Escolha o arquivo (1-{len(arquivos)}): ").strip())
        if 1 <= escolha <= len(arquivos):
            return os.path.join(diretorio_data, arquivos[escolha - 1])
    except ValueError:
        pass
    
    logger.error("Seleção inválida ou cancelada.")
    return None

def obter_porta_ssh(porta_json: any) -> int:
    """Define a porta SSH baseada em cascata de prioridades."""
    entrada = input(f"\n👉 Porta SSH (Sugerida: {porta_json} | ENTER para confirmar): ").strip()
    
    if entrada.isdigit():
        p = int(entrada)
        if 1 <= p <= 65535: return p
    
    # Fallback para JSON ou padrão 22
    try:
        p_json = int(porta_json)
        return p_json if 1 <= p_json <= 65535 else 22
    except (ValueError, TypeError):
        return 22

# =============================================================================
# FLUXO PRINCIPAL (CORE)
# =============================================================================

def iniciar():
    """Função mestre que orquestra o carregamento, processamento e relatório."""
    diretorio_raiz = os.getcwd()
    diretorio_data = os.path.join(diretorio_raiz, "data")
    loader = ConfigLoader(diretorio_raiz)
    
    print("\n" + "="*60)
    print("🚀 SISTEMA CONTAR - MONITOR DE PTMP V1.0.0")
    print("="*60)

    # 1. Seleção do Arquivo
    caminho_json = selecionar_arquivo_json(diretorio_data)
    if not caminho_json: return

    try:
        # 2. Carregamento e Validação de Estrutura
        json_data = loader.load_json_data(caminho_json)
        if not isinstance(json_data, dict) or "LISTA_RADIOS" not in json_data:
            logger.error("Estrutura do JSON inválida. Chave 'LISTA_RADIOS' é obrigatória.")
            return

        # 3. Credenciais e Metadados
        meta = json_data.get("METADADOS", {})
        regiao = meta.get("regiao", "PADRAO").upper()
        user, password = loader.get_credentials(regiao)
        
        if not user or not password:
            logger.error(f"Credenciais para '{regiao}' não encontradas no arquivo .env")
            return

        # 4. Configuração de Rede
        porta_final = obter_porta_ssh(meta.get("porta_padrao"))
        logger.info(f"Configurado: Região={regiao} | Porta={porta_final}")

        # 5. Filtragem e Mapeamento de Tarefas
        lista_tarefas = []
        for radio in json_data["LISTA_RADIOS"]:
            ip_validado = validar_e_normalizar_ip(radio.get("ip"))
            if ip_validado:
                lista_tarefas.append(RadioTask(
                    ip=ip_validado,
                    torre=radio.get("torre", "Desconhecida"),
                    username=user,
                    password=password,
                    port=porta_final
                ))
        
        total = len(lista_tarefas)
        if total == 0:
            logger.error("Nenhum rádio com IP válido para processar.")
            return

        # 6. Execução do Motor de Processamento
        print(f"\n⚡ Iniciando varredura em {total} dispositivos...")
        
        def atualizar_progresso(n):
            prog = min((n / total) * 100, 100)
            print(f"   [Progresso: {n}/{total} ({prog:.1f}%)]", end='\r', flush=True)

        engine = ProcessamentoEngine(max_workers=25)
        resultados = engine.processar_radios(lista_tarefas, callback_progresso=atualizar_progresso)
        print(" " * 60, end='\r') # Limpa linha de progresso

        # 7. Relatório Final
        nome_relatorio = f"Contagem_{regiao}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        ExcelGenerator.gerar_relatorio(resultados, nome_relatorio)
        
        # Resumo Estatístico
        on = sum(1 for r in resultados if r.status == 'Online')
        print("\n" + "="*60)
        print(f"✅ CONCLUÍDO COM SUCESSO")
        print(f"   🟢 Online: {on} | 🔴 Offline: {total - on}")
        print(f"   📄 Arquivo: {nome_relatorio}")
        print("="*60 + "\n")

    except json.JSONDecodeError:
        logger.error(f"Erro de sintaxe no arquivo JSON: {caminho_json}")
    except KeyboardInterrupt:
        print("\n⚠️ Operação interrompida pelo usuário.")
    except Exception as e:
        logger.critical(f"Falha inesperada: {e}", exc_info=True)

if __name__ == "__main__":
    iniciar()