import pandas as pd
import logging
from typing import List
from datetime import datetime
from app.models.data_models import RadioResult

logger = logging.getLogger(__name__)

class ExcelGenerator:
    @staticmethod
    def gerar_relatorio(resultados: List[RadioResult], caminho_saida: str) -> str:
        """
        Converte a lista de resultados em um arquivo Excel formatado.
        Retorna o caminho do arquivo gerado.
        """
        try:
            # Converte a lista de Dataclasses para uma lista de dicionários
            dados = [
                {
                    "IP": r.ip,
                    "Torre": r.torre,
                    "Status": r.status,
                    "Clientes": r.clientes,
                    "Observação": r.observacao,
                    "Data/Hora": datetime.now().strftime("%d/%m/%Y %H:%M")
                } 
                for r in resultados
            ]

            df = pd.DataFrame(dados)

            # Ordenação inteligente: primeiro os Offline, depois por quantidade de clientes
            if not df.empty:
                df = df.sort_values(by=["Status", "Clientes"], ascending=[False, False])

            # Salva o arquivo
            df.to_excel(caminho_saida, index=False, engine='openpyxl')
            
            logger.info(f"Relatório gerado com sucesso: {caminho_saida}")
            return caminho_saida

        except PermissionError:
            logger.error("Erro de permissão: O arquivo Excel pode estar aberto.")
            raise PermissionError("Não foi possível salvar o arquivo. Feche o Excel e tente novamente.")
        except Exception as e:
            logger.error(f"Erro ao gerar Excel: {e}")
            raise RuntimeError(f"Falha na geração do relatório: {e}")