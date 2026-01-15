import os
import sys
import json
import logging
import ipaddress
from datetime import datetime
from app.utils.config_loader import ConfigLoader
from app.core.engine import ProcessamentoEngine
from app.utils.excel_generator import ExcelGenerator
from app.models.data_models import RadioTask

# Configuração de Logging com Rotação
from logging.handlers import RotatingFileHandler

# Criar diretório de logs se não existir
os.makedirs('logs', exist_ok=True)

log_handler = RotatingFileHandler('logs/app.log', maxBytes=1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[log_handler, logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def validar_e_normalizar_ip(ip_str: str) -> str | None:
    """
    Valida e normaliza endereços IP (IPv4 e IPv6).
    
    Args:
        ip_str: String contendo o IP (pode incluir porta)
    
    Returns:
        IP normalizado ou None se inválido
    """
    if not ip_str or not isinstance(ip_str, str):
        return None
    
    ip_limpo = ip_str.strip()
    
    # Remove porta em IPv6 [::1]:porta
    if '[' in ip_limpo and ']' in ip_limpo:
        ip_limpo = ip_limpo.split(']')[0].replace('[', '')
    # Remove porta em IPv4 192.168.1.1:22
    elif ':' in ip_limpo and ip_limpo.count(':') == 1:
        ip_limpo = ip_limpo.split(':')[0]
    
    try:
        return str(ipaddress.ip_address(ip_limpo))
    except ValueError as e:
        logger.debug(f"IP inválido '{ip_str}': {e}")
        return None


def validar_porta(entrada: str, porta_json: int = None, padrao: int = 22) -> int:
    """
    Valida porta com cascata de prioridades.
    
    Ordem de prioridade:
    1. Entrada do usuário
    2. Porta do JSON
    3. Padrão (22)
    
    Args:
        entrada: Entrada do usuário
        porta_json: Porta sugerida pelo JSON
        padrao: Porta padrão (22)
    
    Returns:
        Porta validada (1-65535)
    """
    # Prioridade 1: Entrada do usuário
    if entrada and entrada.isdigit():
        p = int(entrada)
        if 1 <= p <= 65535:
            logger.info(f"Usando porta do input: {p}")
            return p
        else:
            logger.warning(f"Porta {p} fora do intervalo [1-65535], descartada")
    
    # Prioridade 2: Porta do JSON
    if porta_json:
        try:
            p = int(porta_json)
            if 1 <= p <= 65535:
                logger.info(f"Usando porta do JSON: {p}")
                return p
            else:
                logger.warning(f"Porta do JSON {p} inválida, usando padrão")
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao converter porta JSON '{porta_json}': {e}")
    
    # Prioridade 3: Padrão
    logger.info(f"Usando porta padrão: {padrao}")
    return padrao


def iniciar():
    """Função principal do sistema."""
    diretorio_raiz = os.getcwd()
    loader = ConfigLoader(diretorio_raiz)
    
    print("\n" + "="*60)
    print("🚀 SISTEMA CONTAR - CORE V0.9.8")
    print("="*60 + "\n")

    try:
        # ========== 1. Carregamento e Validação do JSON ==========
        caminho_json = os.path.join(diretorio_raiz, "data", "radios.json")
        
        if not os.path.exists(caminho_json):
            logger.error(f"Arquivo não encontrado: {caminho_json}")
            return
        
        try:
            json_data = loader.load_json_data(caminho_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON malformado em {caminho_json}: {e}")
            return
        except Exception as e:
            logger.error(f"Erro ao carregar JSON: {e}")
            return
        
        # Validar estrutura mínima
        if not isinstance(json_data, dict):
            logger.error("JSON deve ser um objeto (dict), não foi possível processar")
            return
        
        if "METADADOS" not in json_data or "LISTA_RADIOS" not in json_data:
            logger.error("JSON inválido: Chaves obrigatórias 'METADADOS' ou 'LISTA_RADIOS' não encontradas")
            return
        
        logger.info("✅ JSON carregado e validado com sucesso")

        # ========== 2. Carregamento de Credenciais ==========
        regiao = json_data["METADADOS"].get("regiao", "PADRAO").upper()
        logger.info(f"Região identificada: {regiao}")
        
        user, password = loader.get_credentials(regiao)
        
        if not user or not password:
            logger.error(f"❌ Credenciais para '{regiao}' não encontradas no .env")
            logger.info("Certifique-se de que as variáveis estão configuradas: "
                       f"{regiao}_USER e {regiao}_PASSWORD")
            return
        
        logger.info(f"✅ Credenciais carregadas para {regiao}")

        # ========== 3. Seleção e Validação de Porta ==========
        porta_json = json_data["METADADOS"].get("porta_padrao", 22)
        
        entrada_porta = input(f"\n👉 Porta SSH (Sugerida: {porta_json} | ENTER para usar): ").strip()
        porta_final = validar_porta(entrada_porta, porta_json, 22)
        logger.info(f"Porta final definida: {porta_final}")

        # ========== 4. Mapeamento e Validação de IPs ==========
        lista_tarefas = []
        lista_radios = json_data.get("LISTA_RADIOS", [])
        
        if not isinstance(lista_radios, list) or len(lista_radios) == 0:
            logger.error("LISTA_RADIOS vazia ou inválida")
            return
        
        for idx, radio in enumerate(lista_radios, start=1):
            ip_ok = validar_e_normalizar_ip(radio.get("ip", ""))
            
            if ip_ok:
                lista_tarefas.append(RadioTask(
                    ip=ip_ok,
                    torre=radio.get("torre", "Desconhecida"),
                    username=user,
                    password=password,
                    port=porta_final
                ))
            else:
                logger.warning(f"[Linha {idx}] IP inválido descartado: {radio.get('ip')}")
        
        logger.info(f"Total de rádios válidos: {len(lista_tarefas)}/{len(lista_radios)}")

        # ========== 5. Validação de Tarefas ==========
        total_tarefas = len(lista_tarefas)
        if total_tarefas == 0:
            logger.error("❌ Nenhuma tarefa válida após filtragem. Verifique o arquivo JSON.")
            return
        
        logger.info(f"✅ {total_tarefas} tarefas prontas para processamento")

        # ========== 6. Processamento com Progresso ==========
        def callback_progresso(n: int):
            """Callback seguro para atualizar progresso."""
            porcentagem = (n / total_tarefas) * 100
            # Garante que não ultrapasse 100%
            progresso_visual = min(porcentagem, 100)
            print(f"   [Progresso: {n}/{total_tarefas} ({progresso_visual:.1f}%)]", 
                  end='\r', flush=True)
        
        print("\n🔄 Iniciando processamento...\n")
        engine = ProcessamentoEngine(max_workers=25)
        resultados = engine.processar_radios(lista_tarefas, callback_progresso=callback_progresso)
        
        # Limpa a linha de progresso
        print(" " * 60, end='\r')

        # ========== 7. Geração de Relatório ==========
        print("\n📊 Gerando relatório em Excel...")
        
        if not resultados:
            logger.warning("Nenhum resultado para gerar relatório")
            return
        
        data_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nome_excel = f"Relatorio_{regiao}_{data_str}.xlsx"
        
        try:
            ExcelGenerator.gerar_relatorio(resultados, nome_excel)
            logger.info(f"✅ Relatório gerado: {nome_excel}")
        except Exception as e:
            logger.error(f"Erro ao gerar relatório Excel: {e}", exc_info=True)
            return
        
        # ========== 8. Resumo Final ==========
        online = sum(1 for r in resultados if r.status == 'Online')
        offline = total_tarefas - online
        
        print("\n" + "="*60)
        print(f"✅ PROCESSAMENTO CONCLUÍDO")
        print(f"   🟢 Online: {online}/{total_tarefas}")
        print(f"   🔴 Offline: {offline}/{total_tarefas}")
        print(f"   📄 Relatório: {nome_excel}")
        print("="*60 + "\n")

    except KeyboardInterrupt:
        logger.warning("Operação cancelada pelo usuário (Ctrl+C)")
        print("\n\n⚠️  Processamento interrompido pelo usuário")
    except Exception as e:
        logger.critical(f"❌ Erro fatal: {e}", exc_info=True)
        print(f"\n❌ Erro crítico: {e}")


if __name__ == "__main__":
    iniciar()