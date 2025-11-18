import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class ClassPartDataBase:
    def __init__(self):
        self.connection, self.cursor = self.conectar_banco()
        self.criar_tabela()

    def conectar_banco(self, nome_banco="banco_video_decode.db"):
        caminho_completo = os.path.join(BASE_DIR, nome_banco)
        conexao = sqlite3.connect(caminho_completo)
        cursor = conexao.cursor()
        return conexao, cursor

    def criar_tabela(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trechos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_solicitacao TEXT NOT NULL UNIQUE,
                padrao TEXT NOT NULL,
                tipo INTEGER NOT NULL,
                usuario INTEGER NOT NULL,
                data_inicial TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_final TIMESTAMP
            )
        ''')
        return True

    def inserir_trecho(self, id_solicitacao, usuario, padrao, tipo):
        self.cursor.execute("INSERT INTO trechos (id_solicitacao, usuario, padrao, tipo) VALUES (?, ?, ?, ?)", (id_solicitacao, usuario, padrao, tipo))
        self.connection.commit()
        return self.cursor.rowcount > 0
    
    def deletar_trecho(self, id_solicitacao):
        self.cursor.execute("DELETE FROM trechos WHERE id_solicitacao = ?", (id_solicitacao,))
        self.connection.commit()
        return self.cursor.rowcount > 0
    
    def listar_trechos(self, usuario):
        self.cursor.row_factory = self.dict_factory
        self.cursor.execute("SELECT * FROM trechos WHERE usuario = ?", (usuario,))
        return self.cursor.fetchall()
    
    def listar_trecho_usuario(self, id_solicitacao):
        self.cursor.row_factory = self.dict_factory
        self.cursor.execute("SELECT * FROM trechos WHERE id_solicitacao = ?", (id_solicitacao,))
        return self.cursor.fetchone()
    
    def listar_usuario(self, id_solicitation):
        self.cursor.row_factory = self.dict_factory
        self.cursor.execute("SELECT usuario FROM trechos WHERE id_solicitacao = ?", (id_solicitation,))
        usuario = self.cursor.fetchone()
        return usuario['usuario']
    
    def registrar_fim(self, timestamp, id_solicitacao):
        self.cursor.execute("UPDATE trechos SET data_final = ? WHERE id_solicitacao = ?", (timestamp, id_solicitacao,))
        self.connection.commit()
        if self.cursor.rowcount > 0:
            return self.listar_usuario(id_solicitacao)
        return False

    def fechar_conexao(self):
        self.connection.close()
    
    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d