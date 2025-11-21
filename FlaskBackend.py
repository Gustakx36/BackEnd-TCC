from flask import (
    Flask, request as flask_request, jsonify,
    stream_with_context, Response, send_from_directory
)
from DatabaseClass.ClassUserDataBase import ClassUserDataBase
from DatabaseClass.ClassPartDataBase import ClassPartDataBase
from ClassManageAudio import ClassManageAudio
from ClassMonitoriaPasta import VideoHandler
from watchdog.observers import Observer
from flask_socketio import SocketIO
from flask_cors import CORS

import subprocess
import threading
import hashlib
import yt_dlp
import shutil
import json
import math
import time
import re
import os

# --------------------------------------------------------
# Configuração Flask + SocketIO
# --------------------------------------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", ping_interval=10, ping_timeout=30)
CORS(app=app, resources={r"*": {"origins": "*"}})

app_dir = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(app_dir, 'Uploads')
TRECHOS_FOLDER = os.path.join(app_dir, 'Trechos')

# --------------------------------------------------------
# Variáveis globais de estado
# --------------------------------------------------------
processos_ativos = {}
processos_background = {}
processos_principal_ativo = False
recebendo_arquivos = False

# --------------------------------------------------------
# Funções auxiliares
# --------------------------------------------------------
def processamento_video(fileName, pattern, id_solicitation, username, tipo, host, resumo):
    """Processa vídeo: extrai áudio, registra em banco e notifica via SocketIO."""
    global processos_background, processos_ativos

    ClassManageAudio(fileName, pattern, id_solicitation, host).extract_audio(int(tipo), resumo)

    connection = ClassPartDataBase()
    connectionUsuario = ClassUserDataBase()
    usuario = connection.registrar_fim(int(time.time()), id_solicitation)
    sessao = connectionUsuario.retorna_sessao(usuario)

    connection.fechar_conexao()
    connectionUsuario.fechar_conexao()

    if os.path.exists(fileName):
        os.remove(fileName)

    socketio.emit('finalizou_processo', {'id_solicitation': id_solicitation}, room=sessao)

    if username in processos_ativos:
        observer = processos_ativos.pop(username)
        observer.stop()


def valida_processo_livre():
    """Verifica se já existe processo principal ativo."""
    return bool(processos_principal_ativo)


def extract_numbers(filename):
    """Extrai números de nomes de arquivos (para ordenação)."""
    numbers = re.findall(r'\d+', filename)
    return tuple(map(int, numbers))


def progress_hook(d, id_solicitation=None, username=None):
    """Hook de progresso de download (yt_dlp)."""
    connectionUsuario = ClassUserDataBase()
    sessao = connectionUsuario.retorna_sessao(username)

    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        percent = math.ceil((downloaded / total * 100)) if total > 0 else 0

        data = {
            "status": "downloading",
            "percent": percent,
            "speed": d.get('_speed_str', '0.0 KiB/s'),
            "eta": d.get('_eta_str', '00:00'),
            "id_solicitation": id_solicitation
        }

    elif d['status'] == 'finished':
        data = {
            "status": "finished",
            "percent": 100,
            "id_solicitation": id_solicitation
        }

    socketio.emit("download_progress", data, room=sessao)


def start_process(nome_arquivo, pattern, id_solicitation, username, tipo, host, resumo):
    """Inicia thread de processamento de vídeo."""
    fileName = os.path.join(UPLOAD_FOLDER, nome_arquivo).replace("\\", "\\\\")
    thread = threading.Thread(
        target=processamento_video,
        args=(fileName, pattern, id_solicitation, username, tipo, host, resumo),
        daemon=True
    )
    thread.start()
    return True


def pagina(id_solicitation):
    """Retorna string indicando progresso da geração dos trechos."""
    arquivos = os.listdir(os.path.join(app_dir, "Audios"))
    filtrados = sorted(
        [f for f in arquivos if f.startswith(str(id_solicitation))],
        key=lambda x: int(x.split("_")[1].split(".")[0])
    )

    if not filtrados:
        return ''

    primeiro, ultimo = filtrados[0], filtrados[-1]
    tamanho = int(ultimo.split("_")[1].split(".")[0])
    pagina = int(primeiro.split("_")[1].split(".")[0])

    return f'Analisando Trechos {pagina}/{tamanho}'

# --------------------------------------------------------
# Rotas Flask
# --------------------------------------------------------


@app.route('/upload_youtube', methods=['POST'])
def upload_file_youtube():
    """Baixa vídeo do YouTube e inicia processamento."""

    if valida_processo_livre():
        return jsonify({'status': False, 'message': 'Fila com processos ativos, aguarde!!'}), 200

    dados = flask_request.get_json()
    id_solicitation = dados.get('id_solicitation')
    pattern = dados.get('padrao')
    username = dados.get('username')
    tipo = dados.get('tipo')
    url_youtube = dados.get('url_youtube')
    resumo = dados.get('resumo')

    fileName = os.path.join(UPLOAD_FOLDER, id_solicitation)

    ydl_opts = {
        'outtmpl': fileName,
        'format': 'bestvideo+bestaudio/best',
        'progress_hooks': [
            lambda d: progress_hook(d, id_solicitation=id_solicitation, username=username)
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url_youtube, download=True)
        nome_arquivo = f"{id_solicitation}.{info['ext']}"

    start_process(nome_arquivo, pattern, id_solicitation, username, tipo, f'{flask_request.host}/backend', resumo)
    return jsonify({'status': True}), 200


@app.route('/criar_trecho_banco_monitoria', methods=['GET'])
def criar_trecho_banco_monitoria():
    """Cria monitoramento de pasta para novos trechos."""
    global processos_ativos, processos_background

    id_solicitation = flask_request.args.get('id_solicitation')
    username = flask_request.args.get('username')
    padrao = flask_request.args.get('padrao')
    tipo = flask_request.args.get('tipo')

    pasta_monitorada = os.path.join(app_dir, f'Trechos/{id_solicitation}')
    os.makedirs(pasta_monitorada, exist_ok=True)

    observer = Observer()
    observer.schedule(VideoHandler(username, f'{flask_request.host}/backend'), pasta_monitorada, recursive=False)
    observer.start()

    processos_ativos[username] = observer
    processos_background[id_solicitation] = []

    connection = ClassPartDataBase()
    connection.inserir_trecho(id_solicitation, username, padrao, tipo)
    connection.fechar_conexao()

    return jsonify({'status': True}), 200


@app.route('/arquivo_trecho', methods=['GET'])
def start_process_part():
    """Lista arquivos de trechos criados e retorna metadados."""
    global recebendo_arquivos
    recebendo_arquivos = True

    file_path = os.path.join(TRECHOS_FOLDER, flask_request.args.get('id_solicitation'))
    connection = ClassPartDataBase()
    dados = connection.listar_trecho_usuario(flask_request.args.get('id_solicitation'))

    itens = sorted(
        [f for f in os.listdir(file_path) if os.path.isfile(os.path.join(file_path, f))],
        key=extract_numbers
    )

    return jsonify({
        'response': len(itens),
        'arquivos': itens,
        'dados': dados
    }), 200


@app.route('/paginas', methods=['GET'])
def paginas():
    """Notifica nova página criada de trecho para o usuário."""
    connection = ClassPartDataBase()
    usuario = connection.listar_usuario(flask_request.args.get('id_solicitation'))
    connectionUsuario = ClassUserDataBase()
    sessao = connectionUsuario.retorna_sessao(usuario)

    socketio.emit(
        'pagina_nova',
        {
            'pagina': pagina(flask_request.args.get("id_solicitation")),
            'id_solicitation': flask_request.args.get('id_solicitation')
        }, 
        room=sessao
    )
    return jsonify({}), 200


@app.route('/status', methods=['GET'])
def status():
    """Notifica status atual do processamento ao usuário."""
    connection = ClassPartDataBase()
    usuario = connection.listar_usuario(flask_request.args.get('id_solicitation'))
    connectionUsuario = ClassUserDataBase()
    sessao = connectionUsuario.retorna_sessao(usuario)

    socketio.emit(
        'pagina_nova', 
        {
            'pagina': flask_request.args.get("status"),
            'id_solicitation': flask_request.args.get('id_solicitation')
        },
        room=sessao
    )
    return jsonify({}), 200


@app.route('/fila_trechos', methods=['GET'])
def fila_trechos():
    """Adiciona arquivos à fila de trechos a serem processados."""
    global recebendo_arquivos
    connection = ClassUserDataBase()
    socketio.emit(
        'file_found', 
        {
            'fileName': flask_request.args.get('file_url'), 
            'id_solicitation': flask_request.args.get('id_solicitation')
        }, 
        room=connection.retorna_sessao(flask_request.args.get('username'))
    )
    connection.fechar_conexao()
    return jsonify({'status': recebendo_arquivos}), 200


# @app.route('/video_low/<id_solicitation>/<filename>', methods=['GET'])
# def get_video(id_solicitation, filename):
#     """Serve vídeo original de um trecho."""
#     path = os.path.join("Trechos", id_solicitation, filename)
#     if not os.path.exists(path):
#         return "Arquivo não encontrado", 404

#     command = [
#         "ffmpeg", "-i", path,
#         "-c:v", "libx264", "-preset", "medium",
#         "-crf", "25",
#         "-vf", "scale='min(854,iw)':-2",    # no máx 480p
#         "-c:a", "aac", "-b:a", "64k",
#         "-movflags", "frag_keyframe+empty_moov",
#         "-f", "mp4", "pipe:1"
#     ]

#     process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

#     return Response(
#         stream_with_context(process.stdout),
#         mimetype="video/mp4",
#         direct_passthrough=True
#     )


@app.route('/video/<id_solicitation>/<filename>', methods=['GET'])
def get_video_low(id_solicitation, filename):
    """Serve um vídeo existente direto da pasta"""
    dir_path = os.path.join(app_dir, "Trechos", id_solicitation)

    if not os.path.exists(os.path.join(dir_path, filename)):
        return "Arquivo não encontrado", 404

    return send_from_directory(directory=dir_path, path=filename, mimetype="video/mp4")

@app.route('/audio/<id_solicitation>', methods=['GET'])
def get_audio(id_solicitation):
    """Serve apenas o áudio extraído do trecho."""
    path = os.path.join(app_dir, "Trechos", id_solicitation)
    if not os.path.exists(path):
        return "Arquivo não encontrado", 404

    return send_from_directory(path, "audio/audio.mp3", mimetype="audio/mpeg")

@app.route('/delete/<id_solicitation>', methods=['DELETE'])
def delete_trecho(id_solicitation):
    path = os.path.join(app_dir, "Trechos", id_solicitation)

    if not os.path.exists(path):
        return jsonify({"error": path}), 404

    try:
        shutil.rmtree(path)
        connection = ClassPartDataBase()
        connection.deletar_trecho(id_solicitation)
        connection.fechar_conexao()
        return jsonify({"message": f"Trecho '{id_solicitation}' removido com sucesso"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trechos_criados', methods=['GET'])
def get_trechos_criados():
    """Retorna lista de trechos criados para o usuário."""
    connection = ClassPartDataBase()
    trechos = connection.listar_trechos(flask_request.args.get('username'))
    connection.fechar_conexao()
    return jsonify(trechos), 200

@app.route("/get-json/<id_solicitation>", methods=["GET"])
def get_json(id_solicitation):
    file_path = os.path.join(os.path.dirname(__file__), f"Trechos/{id_solicitation}/json/json.json")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return jsonify(data), 200

@app.route("/get-resumo/<id_solicitation>", methods=["GET"])
def get_resumo(id_solicitation):
    file_path = os.path.join(
        os.path.dirname(__file__),
        f"Trechos/{id_solicitation}/txt/texto_resumo.txt"
    )

    if not os.path.exists(file_path):
        return jsonify({"status": False}), 200

    with open(file_path, "r", encoding="utf-8") as f:
        conteudo = f.read()

    return jsonify({"status": True, "resumo": conteudo}), 200

@app.route("/valida_acesso/<usuario>")
def valida_acesso(usuario):
    """Endpoint de saúde (ping/pong)."""
    connection = ClassUserDataBase()
    print(connection.listar_usuario(usuario))
    if connection.listar_usuario(usuario):
        return {"status": True}, 200
    return {"status": False}, 200

@app.route("/ping")
def ping():
    """Endpoint de saúde (ping/pong)."""
    import os
    data = os.urandom(1 * 512 * 512)
    return data, 200, {"Content-Type": "application/octet-stream"}

@app.route("/check")
def check():
    """Endpoint de saúde (ping/pong)."""
    return {"1":"1"}, 200
# --------------------------------------------------------
# Eventos SocketIO
# --------------------------------------------------------
@socketio.on("senhaMD5")
def handle_connect(data):
    """Evento de login com senha MD5."""
    connection = ClassUserDataBase()
    if connection.valida_usuario_md5(data["nome"], data['senha']):
        return socketio.emit('reset', {"error": True, "message": 'Senha Incorreta!'}, to=flask_request.sid)
    socketio.emit(
        'logar',
        {'username': data["nome"], 'senha': hashlib.md5(data["senha"].encode()).hexdigest()},
        to=flask_request.sid
    )
    connection.registrar_sessao(data["nome"], flask_request.sid)
    connection.fechar_conexao()


@socketio.on('conn')
def handle_conn(data):
    """Evento de conexão autenticada."""
    connection = ClassUserDataBase()
    if connection.valida_usuario(data["nome"], data['senha']):
        return socketio.emit('reset', {"error": False}, to=flask_request.sid)

    socketio.emit(
        'logar',
        {'username': data["nome"], 'senha': data["senha"]},
        to=flask_request.sid
    )
    connection.registrar_sessao(data["nome"], flask_request.sid)
    connection.fechar_conexao()


@socketio.on("connect")
def handle_validar():
    """Validação de acesso em nova conexão."""
    socketio.emit('valida acesso', to=flask_request.sid)

# --------------------------------------------------------
# Inicialização
# --------------------------------------------------------
if __name__ == '__main__':
    socketio.run(app, host='10.0.0.2', port=5000)
