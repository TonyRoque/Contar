import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Optional
from app.models.data_models import RadioTask, RadioResult
from app.network.ssh_client import SSHManager

logger = logging.getLogger(__name__)

class ProcessamentoEngine:
    def __init__(self, max_workers: int = 20):
        self.max_workers = max_workers
        self.ssh_manager = SSHManager()

    def processar_radios(
        self, 
        tarefas: List[RadioTask], 
        callback_progresso: Optional[Callable[[int], None]] = None
    ) -> List[RadioResult]:
        """
        Orquestra a execução paralela das consultas nos rádios.
        
        :param tarefas: Lista de objetos RadioTask.
        :param callback_progresso: Função opcional para atualizar a UI (progresso).
        :return: Lista de objetos RadioResult.
        """
        resultados = []
        total = len(tarefas)
        concluidos = 0

        logger.info(f"Iniciando processamento de {total} rádios com {self.max_workers} threads.")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Mapeia cada tarefa para o método contar_clientes do ssh_manager
            future_to_radio = {
                executor.submit(self.ssh_manager.contar_clientes, task): task 
                for task in tarefas
            }

            for future in as_completed(future_to_radio):
                try:
                    resultado = future.result()
                    resultados.append(resultado)
                except Exception as e:
                    # Este bloco captura erros catastróficos que o SSHManager não pegou
                    task = future_to_radio[future]
                    logger.error(f"Erro fatal ao processar rádio {task.ip}: {e}")
                    resultados.append(RadioResult(
                        ip=task.ip, 
                        torre=task.torre, 
                        status="Erro Interno", 
                        observacao=str(e)
                    ))
                finally:
                    concluidos += 1
                    if callback_progresso:
                        # Envia o progresso atual (ex: 1, 2, 3...) para quem chamou
                        callback_progresso(concluidos)

        return resultados