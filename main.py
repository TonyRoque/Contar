import os
import logging
from app.utils.config_loader import ConfigLoader
from app.core.engine import ProcessamentoEngine
from app.utils.excel_generator import ExcelGenerator
from app.models.data_models import RadioTask

# Configuração de Logs para acompanhar o processamento no console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def iniciar():
    # 1. Setup Inicial e Carregamento de Ambiente
    # Define a pasta raiz onde o script está sendo executado
    diretorio_raiz = os.getcwd()
    loader = ConfigLoader(diretorio_raiz)
    
    print("\n" + "="*40)
    print("🚀 SISTEMA CONTAR - MONITOR DE PTMP")
    print("="*40 + "\n")

    try:
        # 2. Carregar o arquivo JSON (Ajuste o nome do seu arquivo abaixo)
        caminho_json = os.path.join(diretorio_raiz, "data", "radios.json")
        json_data = loader.load_json_data(caminho_json)
        
        # 3. Detectar Região e Buscar Credenciais no .env
        metadados = json_data.get("METADADOS", {})
        regiao = metadados.get("regiao", "PADRAO")
        user, password = loader.get_credentials(regiao)
        
        print(f"📍 Região Detectada: {regiao}")
        print(f"👤 Usuário Vinculado: {user}")

        # 4. Interação com o Usuário: Definição da Porta
        # Implementação da sua ideia de perguntar a porta dinamicamente
        entrada_porta = input("\n👉 Digite a porta SSH para este acesso (ou pressione ENTER para 22): ").strip()
        porta_final = int(entrada_porta) if entrada_porta.isdigit() else 22
        
        # 5. Mapeamento dos Dados para o Modelo RadioTask
        lista_tarefas = []
        # Usando a nova estrutura de "LISTA_RADIOS" que simplificamos
        radios_brutos = json_data.get("LISTA_RADIOS", [])
        
        for r in radios_brutos:
            # Garante que o IP esteja limpo (sem portas residuais do JSON antigo)
            ip_limpo = r["ip"].split(":")[0] if ":" in r["ip"] else r["ip"]
            
            lista_tarefas.append(RadioTask(
                ip=ip_limpo,
                torre=r.get("torre", "Desconhecida"),
                username=user,
                password=password,
                port=porta_final
            ))

        if not lista_tarefas:
            print("⚠️ Nenhum rádio encontrado na LISTA_RADIOS do JSON.")
            return

        # 6. Execução via Engine (Multi-Threading)
        print(f"\n⚡ Iniciando varredura em {len(lista_tarefas)} dispositivos...")
        engine = ProcessamentoEngine(max_workers=20)
        
        # O callback atualiza o progresso na mesma linha do terminal
        def atualizar_progresso(n):
            print(f"   [Progresso: {n}/{len(lista_tarefas)} concluídos]", end='\r')

        resultados = engine.processar_radios(lista_tarefas, callback_progresso=atualizar_progresso)

        # 7. Finalização e Geração de Relatório
        print("\n\n📊 Gerando relatório Excel...")
        
        data_atual = metadados.get("data_geracao", "relatorio").replace("/", "-")
        nome_excel = f"Contagem_{regiao}_{data_atual}.xlsx"
        
        ExcelGenerator.gerar_relatorio(resultados, nome_excel)
        
        print(f"✨ CONCLUÍDO! Arquivo salvo como: {nome_excel}")
        print("="*40)

    except FileNotFoundError as e:
        logger.error(f"Arquivo não encontrado: {e}")
    except ValueError as e:
        logger.error(f"Erro nos dados: {e}. Verifique o JSON ou a porta digitada.")
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    iniciar()