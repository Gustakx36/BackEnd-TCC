from watchdog.events import FileSystemEventHandler
import requests
import os

class VideoHandler(FileSystemEventHandler):
    def __init__(self, username, host):
        self.username = username
        self.host = host

    def on_created(self, event):
        if not event.is_directory:
            caminho_completo = event.src_path
            pasta = os.path.basename(os.path.dirname(caminho_completo))
            arquivo = os.path.basename(caminho_completo)
            headers = {'Connection': 'keep-alive'}
            requests.get(f'https://{self.host}/fila_trechos?file_url={arquivo}&id_solicitation={pasta}&username={self.username}', headers=headers)
        