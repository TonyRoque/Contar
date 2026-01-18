import ipaddress
import re
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class IPValidator:
    """Validador de IPs com logging estruturado e tratamento de erros."""
    
    @staticmethod
    def validar_e_normalizar_ip(ip_str: str, strict: bool = False) -> Optional[str]:
        """
        Valida e normaliza strings de IP com logging detalhado.
        
        Args:
            ip_str: String de IP para validar
            strict: Se True, rejeita IPs privados
            
        Returns:
            IP normalizado (str) ou None se inválido
            
        Examples:
            >>> IPValidator.validar_e_normalizar_ip("192.168.1.1")
            '192.168.1.1'
            >>> IPValidator.validar_e_normalizar_ip("invalid") is None
            True
        """
        # Validação de entrada
        if not ip_str:
            logger.debug("IP vazio fornecido")
            return None
        
        if not isinstance(ip_str, str):
            logger.warning(f"Tipo inválido para IP: {type(ip_str).__name__}. Esperado: str")
            return None
        
        # Limpeza de entrada: remove portas, brackets IPv6, espaços
        ip_limpo = ip_str.strip().split(':')[0].replace('[', '').replace(']', '')
        
        try:
            ip_obj = ipaddress.ip_address(ip_limpo)
            
            # Modo strict: rejeita IPs privados
            if strict and ip_obj.is_private:
                logger.warning(f"IP privado rejeitado (strict mode): {ip_limpo}")
                return None
            
            ip_normalizado = str(ip_obj)
            logger.debug(f"IP validado: {ip_str!r} → {ip_normalizado}")
            
            return ip_normalizado
            
        except ValueError as e:
            logger.warning(f"IP inválido: {ip_limpo!r} - {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao validar IP {ip_limpo!r}: {e}", exc_info=True)
            return None


def extrair_tarefas_recursivo(
    dados: Any,
    contexto_pai: str = "Desconhecida"
) -> List[Dict[str, Any]]:
    """
    Varre estrutura JSON recursivamente extraindo IPs e nomes de torres.
    
    Args:
        dados: Estrutura de dados (dict, list, ou primitivo)
        contexto_pai: Contexto para metadata (nome da torre, etc)
        
    Returns:
        Lista de dicionários com: {"ip": str, "torre": str}
        
    Example:
        >>> data = {"RJ": [{"ip": "192.168.1.1"}, {"ip": "192.168.1.2"}]}
        >>> tarefas = extrair_tarefas_recursivo(data)
        >>> len(tarefas)
        2
    """
    tarefas_encontradas = []
    
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            # Ignora metadados
            if chave == "METADADOS":
                continue
            
            # Processa lista de itens
            if isinstance(valor, list):
                for item in valor:
                    if isinstance(item, dict) and "ip" in item:
                        ip_validado = IPValidator.validar_e_normalizar_ip(item.get("ip"))
                        
                        if ip_validado:
                            tarefas_encontradas.append({
                                "ip": ip_validado,
                                "torre": chave,
                                "nome": item.get("nome", "N/A")
                            })
                        else:
                            logger.warning(f"IP inválido em {chave}: {item.get('ip')}")
            else:
                # Recursão para valores que não são listas
                tarefas_encontradas.extend(
                    extrair_tarefas_recursivo(valor, chave)
                )
    
    elif isinstance(dados, list):
        for item in dados:
            tarefas_encontradas.extend(
                extrair_tarefas_recursivo(item, contexto_pai)
            )
    
    return tarefas_encontradas


def gerar_relatorio_txt(resultados: List[Dict[str, Any]]) -> str:
    """
    Gera relatório em texto formatado dos resultados.
    
    Args:
        resultados: Lista de dicionários com resultados
        
    Returns:
        String formatada com relatório
    """
    if not resultados:
        return "Nenhum resultado disponível."
    
    linhas = [
        "╔════════════════════════════════════════════════════════════════╗",
        "║            RELATÓRIO DE VARREDURA DE RÁDIOS                    ║",
        "╠════════════════════════════════════════════════════════════════╣",
    ]
    
    for r in resultados:
        ip = r.get("ip", "N/A")
        status = r.get("status", "Desconhecido")
        clientes = r.get("clientes", 0)
        erro = r.get("erro", "")
        
        linha = f"║ {ip:<15} | {status:<15} | Clientes: {clientes:<3} "
        
        if erro:
            linha += f"| {erro[:25]}"
        
        linhas.append(linha)
    
    linhas.append("╚════════════════════════════════════════════════════════════════╝")
    
    return "\n".join(linhas)