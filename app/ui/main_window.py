import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import logging
import os
from datetime import datetime

# Importações dos módulos refatorados
from app.utils.config_loader import ConfigLoader
from app.core.engine import ProcessamentoEngine
from app.models.data_models import RadioTask
from app.utils.excel_generator import ExcelGenerator
from app.utils.helpers import extrair_tarefas_recursivo, validar_e_normalizar_ip

class CustomHandler(logging.Handler):
    """Encaminha logs do sistema diretamente para a caixa de texto da UI"""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        # Usa o after para garantir que a atualização ocorra na thread principal da UI
        self.text_widget.after(0, self.append_log, msg)

    def append_log(self, msg):
        self.text_widget.insert("end", msg + "\n")
        self.text_widget.see("end")

class ContarApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SISTEMA CONTAR - V1.1.0 (Desktop)")
        self.geometry("850x650")
        ctk.set_appearance_mode("dark")
        
        # Localiza a raiz do projeto para o ConfigLoader encontrar o .env
        diretorio_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.loader = ConfigLoader(diretorio_raiz)
        self.caminho_json = None

        self.setup_ui()
        self.setup_logging()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Cabeçalho Estilizado
        self.header = ctk.CTkLabel(self, text="📡 SISTEMA CONTAR - INVENTÁRIO", font=("Roboto", 24, "bold"))
        self.header.grid(row=0, column=0, pady=(20, 10))

        # Container de Controles
        self.ctrl_frame = ctk.CTkFrame(self)
        self.ctrl_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.btn_select = ctk.CTkButton(self.ctrl_frame, text="Selecionar JSON", command=self.buscar_arquivo, fg_color="#3a7ebf")
        self.btn_select.pack(side="left", padx=10, pady=15)

        self.lbl_file = ctk.CTkLabel(self.ctrl_frame, text="Nenhum arquivo carregado", text_color="gray")
        self.lbl_file.pack(side="left", padx=10)

        self.entry_port = ctk.CTkEntry(self.ctrl_frame, placeholder_text="Porta SSH (Ex: 22)", width=150)
        self.entry_port.pack(side="right", padx=10)

        # Terminal de Logs
        self.txt_log = ctk.CTkTextbox(self, font=("Consolas", 12), border_width=2)
        self.txt_log.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")

        # Barra de Progresso
        self.progress = ctk.CTkProgressBar(self, height=15)
        self.progress.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.progress.set(0)

        # Botão Principal
        self.btn_run = ctk.CTkButton(self, text="▶ INICIAR PROCESSAMENTO", fg_color="#28a745", hover_color="#218838", 
                                     height=50, font=("Roboto", 16, "bold"), command=self.iniciar_thread)
        self.btn_run.grid(row=4, column=0, padx=20, pady=20)

    def setup_logging(self):
        handler = CustomHandler(self.txt_log)
        handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def buscar_arquivo(self):
        path = filedialog.askopenfilename(filetypes=[("Arquivos JSON", "*.json")])
        if path:
            self.caminho_json = path
            self.lbl_file.configure(text=os.path.basename(path), text_color="white")
            logging.info(f"Arquivo selecionado: {os.path.basename(path)}")

    def iniciar_thread(self):
        if not self.caminho_json:
            messagebox.showwarning("Atenção", "Por favor, selecione um arquivo JSON de inventário.")
            return
        
        self.btn_run.configure(state="disabled")
        self.progress.set(0)
        self.txt_log.delete("0.0", "end")
        
        # Executa em Thread separada para a UI não congelar
        threading.Thread(target=self.processar, daemon=True).start()

    def processar(self):
        try:
            # 1. Carregamento
            json_data = self.loader.load_json_data(self.caminho_json)
            meta = json_data.get("METADADOS", {})
            regiao = meta.get("regiao", "PADRAO").upper()
            
            # 2. Credenciais e Porta
            user, password = self.loader.get_credentials(regiao)
            porta_input = self.entry_port.get().strip()
            porta = int(porta_input) if porta_input.isdigit() else int(meta.get("porta_padrao", 22))

            # 3. Extração via Helpers
            dados_brutos = extrair_tarefas_recursivo(json_data)
            tarefas = []
            for item in dados_brutos:
                ip_ok = validar_e_normalizar_ip(item["ip"])
                if ip_ok:
                    tarefas.append(RadioTask(ip=ip_ok, torre=item["torre"], username=user, password=password, port=porta))

            if not tarefas:
                logging.error("Nenhum rádio válido encontrado no JSON.")
                return

            # 4. Motor de Processamento
            total = len(tarefas)
            logging.info(f"Iniciando varredura em {total} rádios da região {regiao}...")

            def update_progress(concluidos):
                self.progress.set(concluidos / total)

            engine = ProcessamentoEngine(max_workers=20)
            resultados = engine.processar_radios(tarefas, callback_progresso=update_progress)

            # 5. Excel e Finalização
            data_str = datetime.now().strftime('%Y%m%d_%H%M')
            nome_excel = f"Relatorio_{regiao}_{data_str}.xlsx"
            ExcelGenerator.gerar_relatorio(resultados, nome_excel)
            
            sucesso = sum(1 for r in resultados if r.status == "Online")
            logging.info(f"🏆 Finalizado! Sucesso: {sucesso}/{total}. Planilha gerada.")
            messagebox.showinfo("Sucesso", f"Processamento Concluído!\n\nArquivo: {nome_excel}\nSucesso: {sucesso}/{total}")

        except Exception as e:
            logging.error(f"Erro Crítico: {str(e)}")
            messagebox.showerror("Erro no Processamento", f"Ocorreu um erro: {e}")
        finally:
            self.btn_run.configure(state="normal")

if __name__ == "__main__":
    app = ContarApp()
    app.mainloop()