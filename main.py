import streamlit as st
import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

# Importações do projeto
from app.utils.config_loader import ConfigLoader
from app.core.engine import ProcessamentoEngine
from app.utils.helpers import extrair_tarefas_recursivo, IPValidator
from app.utils.excel_generator import ExcelGenerator
from app.utils.constants import NetworkConfig
from app.models.data_models import RadioTask

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# 1. GERENCIADOR DE ENGINE COM TTL (Time To Live)
# ════════════════════════════════════════════════════════════════════════════

class EngineManager:
    """Gerencia lifecycle do Engine com cache e invalidação automática."""
    
    _instance: Optional[ProcessamentoEngine] = None
    _created_at: Optional[datetime] = None
    CACHE_TTL = timedelta(hours=1)  # Invalida a cada hora

    @classmethod
    def get_engine(cls, force_reload: bool = False) -> ProcessamentoEngine:
        """
        Recupera engine com TTL (Time To Live).
        
        Args:
            force_reload: Se True, força recarregamento imediato
            
        Returns:
            Instância de ProcessamentoEngine
        """
        now = datetime.now()

        # Força recarregamento ou TTL expirado
        if force_reload or (
            cls._instance is None
            or (now - cls._created_at) > cls.CACHE_TTL
        ):
            logger.info("🔄 Recarregando Engine (cache expirou ou reload forçado)")
            
            diretorio_raiz = os.path.dirname(os.path.abspath(__file__))
            loader = ConfigLoader(diretorio_raiz)
            cls._instance = ProcessamentoEngine(loader)
            cls._created_at = now

        return cls._instance

    @classmethod
    def reset(cls):
        """Força reset do engine."""
        cls._instance = None
        cls._created_at = None


# ════════════════════════════════════════════════════════════════════════════
# 2. CONFIGURAÇÃO DA PÁGINA
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="CONTAR Dashboard",
    layout="wide",
    page_icon="📡",
    initial_sidebar_state="expanded"
)

# Estilização customizada
st.markdown("""
    <style>
    .reportview-container { background: #0f172a; }
    .stCodeBlock { border-radius: 10px; border: 1px solid #334155; }
    .stSuccess { color: #10b981; }
    .stError { color: #ef4444; }
    .stWarning { color: #f59e0b; }
    </style>
    """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# 3. SIDEBAR (PAINEL DE CONTROLE)
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("⚙️ Painel de Controle")
    st.divider()
    
    # Modo de operação
    modo = st.radio(
        "Modo de operação:",
        ["Leitura (Contagem)", "Análise de Logs"],
        help="Escolha entre processar rádios ou analisar histórico"
    )
    
    # Configurações de performance
    st.subheader("⚡ Performance")
    max_workers = st.slider(
        "Máximo de workers simultâneos",
        min_value=1,
        max_value=20,
        value=NetworkConfig.MAX_WORKERS,
        help="Número de threads paralelas"
    )
    
    timeout_ssh = st.slider(
        "Timeout SSH (segundos)",
        min_value=5,
        max_value=60,
        value=NetworkConfig.SSH_TIMEOUT,
        help="Timeout para cada conexão SSH"
    )
    
    # Botão de reload
    st.divider()
    st.subheader("🔧 Manutenção")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Recarregar Credenciais", use_container_width=True):
            EngineManager.reset()
            st.success("✅ Credenciais recarregadas")
            st.rerun()
    
    with col2:
        if st.button("🧹 Limpar Cache", use_container_width=True):
            st.cache_resource.clear()
            st.success("✅ Cache limpo")
            st.rerun()
    
    st.success("✅ Configurações carregadas!")
    st.caption(f"TTL: {EngineManager.CACHE_TTL.total_seconds()/3600:.0f}h")


# ════════════════════════════════════════════════════════════════════════════
# 4. CONTEÚDO PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

st.title("📡 Orquestrador de Rede CONTAR")
st.markdown("*Sistema de varredura e análise de rádios Ubiquiti com SSH*")

tab_json, tab_pool, tab_resultados = st.tabs([
    "📂 Inventário JSON",
    "🔍 Scanner de IPs",
    "📊 Resultados"
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1: INVENTÁRIO JSON
# ════════════════════════════════════════════════════════════════════════════

with tab_json:
    st.subheader("Carregar inventário JSON")
    
    arquivo_json = st.file_uploader(
        "Selecione o arquivo .json de inventário",
        type=['json'],
        help="Formato: {'TORRE': [{'ip': '192.168.1.1', 'nome': 'RJ1'}]}"
    )
    
    if arquivo_json:
        st.info(f"✅ Arquivo selecionado: {arquivo_json.name}")
        
        try:
            dados = json.load(arquivo_json)
            st.json(dados, expanded=False)
            
            # Extrai tarefas
            tarefas = extrair_tarefas_recursivo(dados)
            st.success(f"📋 {len(tarefas)} tarefas extraídas com sucesso")
            
            # Armazena em session_state para usar depois
            st.session_state.tarefas = tarefas
            st.session_state.modo_entrada = "json"
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Erro ao decodificar JSON: {e}")
        except Exception as e:
            st.error(f"❌ Erro ao processar arquivo: {e}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2: SCANNER DE IPs
# ════════════════════════════════════════════════════════════════════════════

with tab_pool:
    st.subheader("Scanner de Range de IPs")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ip_inicial = st.text_input(
            "IP Inicial",
            placeholder="192.168.1.1",
            help="Primeiro IP do range"
        )
    
    with col2:
        ip_final = st.text_input(
            "IP Final",
            placeholder="192.168.1.254",
            help="Último IP do range"
        )
    
    torre_scan = st.text_input(
        "Nome da Torre (opcional)",
        placeholder="RJ_CENTRAL",
        help="Identificador para agrupar os IPs"
    )
    
    if st.button("🔎 Gerar Range", use_container_width=True):
        try:
            import ipaddress
            
            # Valida IPs
            ip_ini_obj = ipaddress.ip_address(ip_inicial.strip())
            ip_fim_obj = ipaddress.ip_address(ip_final.strip())
            
            if ip_ini_obj > ip_fim_obj:
                st.error("❌ IP inicial deve ser menor que IP final")
            else:
                # Gera range
                ips = [
                    str(ip)
                    for ip in ipaddress.summarize_address_range(ip_ini_obj, ip_fim_obj)
                ]
                
                st.success(f"📋 {len(ips)} IPs gerados")
                st.write(ips[:10] + (["..."] if len(ips) > 10 else []))
                
                # Armazena tarefas
                tarefas = [
                    {"ip": ip, "torre": torre_scan or "SCAN"}
                    for ip in ips
                ]
                
                st.session_state.tarefas = tarefas
                st.session_state.modo_entrada = "scanner"
                
        except ValueError as e:
            st.error(f"❌ IP inválido: {e}")


# ════════════════════════════════════════════════════════════════════════════
# 5. EXECUÇÃO E PROCESSAMENTO
# ════════════════════════════════════════════════════════════════════════════

st.divider()

col_exe, col_export = st.columns([3, 1])

with col_exe:
    executar = st.button(
        "🚀 EXECUTAR TAREFAS",
        use_container_width=True,
        type="primary"
    )

with col_export:
    st.button("📥 Exportar Último Resultado", use_container_width=True)

if executar:
    # Valida se há tarefas
    if not hasattr(st.session_state, 'tarefas') or not st.session_state.tarefas:
        st.error("⚠️ Nenhum arquivo JSON ou range de IP fornecido")
    else:
        # Recupera engine
        try:
            engine = EngineManager.get_engine()
        except Exception as e:
            st.error(f"❌ Erro ao inicializar engine: {e}")
            engine = None

        if engine:
            st.subheader("📋 Processamento em Andamento")
            
            progress_bar = st.progress(0)
            status_container = st.container()
            logs_container = st.container()
            
            tarefas = st.session_state.tarefas
            total_tarefas = len(tarefas)
            
            with logs_container:
                st.info(f"Iniciando processamento de {total_tarefas} tarefas...")
            
            # Processa tarefas
            resultados = engine.processar_em_lote(tarefas)
            
            # Atualiza progresso
            progress_bar.progress(100)
            
            # Armazena resultados
            st.session_state.ultimos_resultados = resultados
            
            # Exibe resumo
            st.divider()
            st.subheader("📊 Resumo de Resultados")
            
            col_online, col_offline, col_erro, col_timeout = st.columns(4)
            
            online = sum(1 for r in resultados if r.get("status") == "Online")
            offline = sum(1 for r in resultados if r.get("status") == "Offline")
            erro = sum(1 for r in resultados if "Erro" in r.get("status", ""))
            timeout = sum(1 for r in resultados if r.get("status") == "Timeout")
            
            with col_online:
                st.metric("✅ Online", online, delta=f"{(online/total_tarefas*100):.1f}%")
            
            with col_offline:
                st.metric("⚫ Offline", offline, delta=f"{(offline/total_tarefas*100):.1f}%")
            
            with col_erro:
                st.metric("❌ Erro", erro, delta=f"{(erro/total_tarefas*100):.1f}%")
            
            with col_timeout:
                st.metric("⏱️ Timeout", timeout, delta=f"{(timeout/total_tarefas*100):.1f}%")
            
            # Tabela de detalhes
            st.subheader("📈 Detalhes Completos")
            df_resultados = pd.DataFrame(resultados)
            st.dataframe(df_resultados, use_container_width=True)
            
            # Exportação
            st.subheader("💾 Exportar Relatório")
            
            col_excel, col_csv = st.columns(2)
            
            with col_excel:
                try:
                    caminho_excel = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    ExcelGenerator.gerar_relatorio(resultados, caminho_excel)
                    st.success(f"✅ Excel gerado: {caminho_excel}")
                    
                    with open(caminho_excel, "rb") as f:
                        st.download_button(
                            "📥 Download Excel",
                            data=f.read(),
                            file_name=caminho_excel,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                except Exception as e:
                    st.error(f"❌ Erro ao gerar Excel: {e}")
            
            with col_csv:
                csv = df_resultados.to_csv(index=False)
                st.download_button(
                    "📥 Download CSV",
                    data=csv,
                    file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )


# ════════════════════════════════════════════════════════════════════════════
# TAB 3: RESULTADOS ANTERIORES
# ════════════════════════════════════════════════════════════════════════════

with tab_resultados:
    st.subheader("Histórico de Resultados")
    
    if hasattr(st.session_state, 'ultimos_resultados') and st.session_state.ultimos_resultados:
        resultados = st.session_state.ultimos_resultados
        df = pd.DataFrame(resultados)
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.multiselect(
                "Filtrar por Status",
                options=df["status"].unique(),
                default=df["status"].unique()
            )
        
        with col2:
            torre_filter = st.multiselect(
                "Filtrar por Torre",
                options=df["torre"].unique(),
                default=df["torre"].unique()
            )
        
        with col3:
            min_clientes = st.number_input("Mínimo de clientes", value=0)
        
        # Aplica filtros
        df_filtrado = df[
            (df["status"].isin(status_filter)) &
            (df["torre"].isin(torre_filter)) &
            (df["clientes"] >= min_clientes)
        ]
        
        st.dataframe(df_filtrado, use_container_width=True)
        st.metric("Total de registros", len(df_filtrado))
    
    else:
        st.info("Nenhum resultado anterior. Execute as tarefas primeiro.")
            log_placeholder.code("\n".join(lista_logs))

        try:
            # --- INTEGRAÇÃO COM SEU MOTOR REAL ---
            import json
            dados = json.load(arquivo_json)
            tarefas = extrair_tarefas_recursivo(dados)
            
            total = len(tarefas)
            atualizar_log(f"Iniciando processamento de {total} rádios...")

            for i, tarefa in enumerate(tarefas):
                atualizar_log(f"Conectando em: {tarefa.ip}...")
                
                # Exemplo: Chamando sua função real do engine
                # resultado = engine.processar_unidade(tarefa) 
                # atualizar_log(f"Resultado {tarefa.ip}: {resultado}")
                
                # Atualiza progresso
                barra_progresso.progress((i + 1) / total)

            st.success("✅ Operação finalizada com sucesso!")
            
        except Exception as e:
            st.error(f"Erro crítico: {e}")