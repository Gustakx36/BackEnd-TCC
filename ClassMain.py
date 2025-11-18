from ClassManageAudio import ClassManageAudio

import tkinter as tk
from tkinter import filedialog, messagebox

def main():
    def selecionar_arquivo():
        arquivo = filedialog.askopenfilename(title="Selecione um arquivo")
        if arquivo:
            label_arquivo.config(text=f"Arquivo: {arquivo}")
            entrada_arquivo.set(arquivo)

    def salvar():
        arquivo = entrada_arquivo.get()
        texto = entrada_texto.get()
        nome = entrada_nome.get()

        if not arquivo:
            messagebox.showerror("Erro", "Nenhum arquivo selecionado!")
            return
        
        if not texto:
            messagebox.showerror("Erro", "Digite um texto!")
            return

        fechar_janela()
        ClassManageAudio(arquivo, texto, nome).extract_audio()

    def fechar_janela():
        janela.destroy()

    janela = tk.Tk()
    janela.title("Upload de Arquivo e Texto")
    janela.geometry("400x200")

    entrada_arquivo = tk.StringVar()
    entrada_texto = tk.StringVar()
    entrada_nome = tk.StringVar()

    btn_arquivo = tk.Button(janela, text="Selecionar Arquivo", command=selecionar_arquivo)
    btn_arquivo.pack(pady=5)

    label_arquivo = tk.Label(janela, text="Nenhum arquivo selecionado")
    label_arquivo.pack(pady=5)

    entry_texto = tk.Entry(janela, textvariable=entrada_texto, width=40)
    entry_texto.pack(pady=5)
    entry_texto.insert(0, "Texto de busca?")

    entrada_nome = tk.Entry(janela, textvariable=entrada_nome, width=40)
    entrada_nome.pack(pady=5)
    entrada_nome.insert(0, "Nome do procedimento?")

    btn_salvar = tk.Button(janela, text="Salvar", command=salvar)
    btn_salvar.pack(pady=10)

    janela.mainloop()

if __name__ == '__main__':
    main()