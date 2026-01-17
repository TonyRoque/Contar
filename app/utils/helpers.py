import ipaddress
import re
import logging

logger = logging.getLogger(__name__)

def validar_e_normalizar_ip(ip_str: str) -> str | None:
    """Limpa e valida strings de IP."""
    if not ip_str or not isinstance(ip_str, str): return None
    # Remove colchetes de IPv6 ou portas residuais
    ip_limpo = ip_str.strip().split(':')[0].replace('[', '').replace(']', '')
    try:
        return str(ipaddress.ip_address(ip_limpo))
    except ValueError:
        return None

def extrair_tarefas_recursivo(dados, contexto_pai="Desconhecida"):
    """Varre o JSON recursivamente em busca de IPs e nomes de torres."""
    tarefas_encontradas = []
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if chave == "METADADOS": continue
            if isinstance(valor, list):
                for item in valor:
                    if isinstance(item, dict) and "ip" in item:
                        tarefas_encontradas.append({
                            "ip": item.get("ip"),
                            "torre": chave
                        })
            else:
                tarefas_encontradas.extend(extrair_tarefas_recursivo(valor, chave))
    elif isinstance(dados, list):
        for item in dados:
            tarefas_encontradas.extend(extrair_tarefas_recursivo(item, contexto_pai))
    return tarefas_encontradas