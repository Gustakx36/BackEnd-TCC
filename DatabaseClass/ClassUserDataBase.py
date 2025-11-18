import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class ClassUserDataBase:
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
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL,
                id_socket TEXT
            )
        ''')
        return True

    def inserir_usuario(self, nome, senha, id_socket=None):
        senha_md5 = self.hash_md5(senha)
        self.cursor.execute("INSERT INTO usuarios (nome, senha, id_socket) VALUES (?, ?, ?)", (nome, senha_md5, id_socket))
        self.connection.commit()
        return self.cursor.rowcount > 0

    def listar_usuario(self, nome):
        self.cursor.row_factory = self.dict_factory
        self.cursor.execute("SELECT * FROM usuarios WHERE nome = ?", (nome,))
        return self.cursor.fetchone()
    
    def valida_usuario_md5(self, nome, senha):
        self.cursor.row_factory = self.dict_factory
        senha_md5 = self.hash_md5(senha)
        self.cursor.execute("SELECT * FROM usuarios WHERE nome = ? AND senha = ?", (nome, senha_md5))
        usuarios = self.cursor.fetchone()
        return usuarios == None
    
    def valida_usuario(self, nome, senha):
        self.cursor.row_factory = self.dict_factory
        self.cursor.execute("SELECT * FROM usuarios WHERE nome = ? AND senha = ?", (nome, senha))
        usuarios = self.cursor.fetchone()
        return usuarios == None
    
    def registrar_sessao(self, nome, id_socket):
        self.cursor.execute("UPDATE usuarios SET id_socket = ? WHERE nome = ?", (id_socket, nome))
        self.connection.commit()
        return self.cursor.rowcount > 0
    
    def retorna_sessao(self, nome):
        self.cursor.row_factory = self.dict_factory
        self.cursor.execute("SELECT id_socket FROM usuarios WHERE nome = ?", (nome,))
        usuario = self.cursor.fetchone()
        return usuario['id_socket']

    def fechar_conexao(self):
        self.connection.close()

    def hash_md5(self, senha):
        return hashlib.md5(senha.encode()).hexdigest()
    
    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d