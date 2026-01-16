import json
import os
import ipaddress
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

class ConversorEstruturaInterna:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Conversor PTMP Pro - v3.5")
        self.root.geometry("550x600")
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Normalizador de Base de Dados", font=("Arial", 14, "bold")).pack(pady=10)
        
        f_top = ttk.Frame(main_frame)
        f_top.pack(fill=tk.X)
        
        ttk.Label(f_top, text="Região:").grid(row=0, column=0, sticky="w", padx=5)
        self.combo_regiao = ttk.Combobox(f_top, values=["RJ", "SP", "ES", "MG"], state="readonly", width=10)
        self.combo_regiao.set("RJ")
        self.combo_regiao.grid(row=1, column=0, padx=5, pady=5)

        ttk.Label(f_top, text="Porta Padrão:").grid(row=0, column=1, sticky="w", padx=5)
        self.entry_porta = ttk.Entry(f_top, width=15)
        self.entry_porta.insert(0, "22")
        self.entry_porta.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=15)
        
        self.btn_converter = tk.Button(main_frame, text="SELECIONAR ARQUIVO E CONVERTER", 
                                       command=self.processar, bg="#27ae60", fg="white", 
                                       font=("Arial", 11, "bold"), height=2)
        self.btn_converter.pack(fill=tk.X, pady=10)

        ttk.Label(main_frame, text="Log de Processamento:").pack(anchor="w")
        self.txt_log = tk.Text(main_frame, height=12, font=("Consolas", 9), state='disabled', bg="#1e1e1e", fg="#00ff00")
        self.txt_log.pack(fill=tk.BOTH, expand=True, pady=5)

    def log(self, mensagem):
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, f" {mensagem}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')
        self.root.update()

    def validar_e_limpar_ip(self, ip_raw):
        """Remove a porta do IP (se houver) e valida."""
        if not ip_raw: return None
        try:
            # Se houver ':', pega apenas o que vem antes (o IP)
            ip_sem_porta = str(ip_raw).split(':')[0].strip()
            ipaddress.ip_address(ip_sem_porta)
            return ip_sem_porta
        except:
            return None

    def extrair_dados(self, caminho):
        dados_temp = {}
        ext = os.path.splitext(caminho)[1].lower()
        sucesso = 0

        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                if ext == ".json":
                    conteudo = json.load(f)
                    
                    # SE O ARQUIVO TIVER A CHAVE "DADOS" (Estrutura que você postou)
                    if isinstance(conteudo, dict) and "DADOS" in conteudo:
                        self.log("Estrutura 'DADOS' detectada.")
                        secao_dados = conteudo["DADOS"]
                        
                        for torre, lista_ips in secao_dados.items():
                            for item in lista_ips:
                                ip_puro = self.validar_e_limpar_ip(item.get("ip"))
                                if ip_puro:
                                    dados_temp.setdefault(torre, []).append({"ip": ip_puro})
                                    sucesso += 1
                    
                    # SE FOR O FORMATO DE LISTA SIMPLES
                    elif isinstance(conteudo, list):
                        for bloco in conteudo:
                            if not isinstance(bloco, dict): continue
                            torre = bloco.get("nome_torre", "DESCONHECIDA").upper()
                            for acesso in bloco.get("acessos", []):
                                ip_puro = self.validar_e_limpar_ip(acesso.get("ip"))
                                if ip_puro:
                                    dados_temp.setdefault(torre, []).append({"ip": ip_puro})
                                    sucesso += 1
                
                elif ext == ".txt":
                    for linha in f:
                        partes = linha.strip().split(";")
                        if len(partes) >= 2:
                            ip_puro = self.validar_e_limpar_ip(partes[0])
                            torre = partes[1].strip().upper()
                            if ip_puro:
                                dados_temp.setdefault(torre, []).append({"ip": ip_puro})
                                sucesso += 1

        except Exception as e:
            self.log(f"ERRO: {str(e)}")

        return dados_temp, sucesso

    def processar(self):
        caminho_in = filedialog.askopenfilename(filetypes=[("Arquivos", "*.txt *.json")])
        if not caminho_in: return

        self.log(f"Processando: {os.path.basename(caminho_in)}")
        dados, ok = self.extrair_dados(caminho_in)
        
        if ok == 0:
            self.log("Nenhum dado válido extraído.")
            messagebox.showwarning("Aviso", "Não foi possível extrair IPs. Verifique o formato do arquivo.")
            return

        regiao = self.combo_regiao.get()
        porta = self.entry_porta.get().strip()
        
        output = {
            "METADADOS": {
                "regiao": regiao,
                "porta_padrao": porta,
                "data_conversao": datetime.now().strftime('%d/%m/%Y %H:%M'),
                "estatisticas": {"salvos": ok}
            },
            "DADOS": dados
        }

        caminho_out = f"{os.path.splitext(caminho_in)[0]}_{regiao}_NOVO.json"
        with open(caminho_out, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)

        self.log(f"CONCLUÍDO! {ok} IPs salvos em {caminho_out}")
        messagebox.showinfo("Sucesso", f"Processado!\nIPs extraídos: {ok}")

if __name__ == "__main__":
    app = ConversorEstruturaInterna()
    app.root.mainloop()