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
        """
        resultados = []
        total = len(tarefas)
        concluidos = 0

        # Log que aparecerá na sua UI
        logger.info(f"🚀 Motor iniciado: Processando {total} rádios com {self.max_workers} canais.")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_radio = {
                executor.submit(self.ssh_manager.contar_clientes, task): task 
                for task in tarefas
            }

            for future in as_completed(future_to_radio):
                task = future_to_radio[future]
                try:
                    resultado = future.result()
                    resultados.append(resultado)
                except Exception as e:
                    logger.error(f"❌ Erro fatal no rádio {task.ip}: {e}")
                    resultados.append(RadioResult(
                        ip=task.ip, 
                        torre=task.torre, 
                        status="Erro Interno", 
                        observacao=str(e)
                    ))
                finally:
                    concluidos += 1
                    if callback_progresso:
                        # O .after(0, ...) no CustomTkinter lidará com isso, 
                        # mas enviamos o valor bruto aqui.
                        callback_progresso(concluidos)

        logger.info(f"✅ Processamento paralelo finalizado.")
        return resultados
        