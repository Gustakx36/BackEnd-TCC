from ClassManageDecode import ClassManageDecode
from ClassManageResume import ClassManageResume
from urllib.parse import urlencode

from scipy.signal import butter, lfilter
from pydub import AudioSegment, effects
from pydub.utils import mediainfo
from moviepy import VideoFileClip
import noisereduce as nr
import soundfile as sf
import numpy as np
import librosa

import subprocess
import requests
import math
import time
import os

class ClassManageAudio:
    def __init__(self, filename, pattern, name_trechos, host):
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.part_dir = os.path.join(self.app_dir, f'Trechos/{name_trechos}')
        os.makedirs(f"{self.app_dir}/Trechos/{name_trechos}/audio", exist_ok=True)
        os.makedirs(f"{self.app_dir}/Trechos/{name_trechos}/metricas", exist_ok=True)
        self.log_metricas = os.path.join(self.app_dir, f'Trechos/{name_trechos}/metricas/metricas.txt')
        self.part_dir_audio = os.path.join(self.app_dir, f'Trechos/{name_trechos}/audio/audio.mp3')
        self.audio_dir = os.path.join(self.app_dir, "Audios")

        self.instance_time = name_trechos
        self.filename = filename
        self.audio = os.path.join(self.audio_dir, f"{self.instance_time}.wav")
        self.pattern = pattern

        self.audio_bruto = os.path.join(self.audio_dir, f"bruto_{self.instance_time}.wav")
        self.audio_mono = os.path.join(self.audio_dir, f"mono_{self.instance_time}.wav")
        
        self.audio_sem_ruido = os.path.join(self.audio_dir, f"sem_ruido_{self.instance_time}.wav")
        self.audio_filtro_aplicado = os.path.join(self.audio_dir, f"filtro_aplicado_{self.instance_time}.wav")
        self.audio_volume_normalizado = os.path.join(self.audio_dir, f"volume_normalizado_{self.instance_time}.wav")

        self.host = host
        
    def extract_audio(self, tipo, resumo = False):
        headers = {'Connection': 'keep-alive'}

        params = {
            "id_solicitation": self.instance_time,
            "status": "Gerando Audio"
        }
        query = urlencode(params)
        requests.get(f'https://{self.host}/status?{query}', headers=headers)

        videoclip = VideoFileClip(self.filename)
        videoclip.audio.write_audiofile(self.audio_bruto, fps=16000, nbytes=2, codec="pcm_s16le")
        videoclip.close()

        params = {
            "id_solicitation": self.instance_time,
            "status": "Iniciando Pré-Processamento"
        }
        query = urlencode(params)
        requests.get(f'https://{self.host}/status?{query}', headers=headers)

        #---------------------------------------------------
        t0 = time.perf_counter()  # Marca o tempo inicial para medir desempenho da etapa

        # Lê o áudio original (pode ter 2 canais: esquerdo e direito)
        data, sr = sf.read(self.audio_bruto)

        # Separa os canais
        canal_esq = data[:, 0]
        canal_dir = data[:, 1]

        # Calcula o valor RMS (Root Mean Square) de cada canal
        rms_esq = np.sqrt(np.mean(canal_esq**2))
        rms_dir = np.sqrt(np.mean(canal_dir**2))

        # Seleciona o canal com maior RMS (ou seja, melhor qualidade/intensidade)
        if rms_esq > rms_dir:
            canal_final = canal_esq
        else:
            canal_final = canal_dir

        # Captura o canal antes do processo para log
        y_pre = canal_esq if rms_esq > rms_dir else canal_dir

        # Salva o canal selecionado como áudio mono (1 canal apenas)
        sf.write(self.audio_mono, canal_final, sr, subtype="PCM_16")

        # Captura o canal após o processo para log
        y_pos, _ = librosa.load(self.audio_mono, sr=16000)

        # Registra o log referente ao processo de seleção de canal Mono
        self._registrar_etapa("Mono", y_pre, y_pos, t0)

        #---------------------------------------------------
        # Marca o tempo inicial para registrar o desempenho desta etapa
        t0 = time.perf_counter()  
        
        # Carrega novamente o áudio para aplicar a redução de ruído
        y, sr = librosa.load(self.audio_mono, sr=16000)
        
        # Aplica redução de ruído espectral, baseada na diferença entre energia da fala e energia do ruído de fundo
        voz_limpa = nr.reduce_noise(
            y=y, 
            sr=sr, 
            prop_decrease=0.25,       # Intensidade de redução (25% do ruído estimado)
            time_mask_smooth_ms=100   # Suavização temporal para evitar distorções abruptas
        )
        
        # Salva o áudio resultante já com ruído reduzido
        sf.write(self.audio_sem_ruido, voz_limpa, sr)
        
        # Registra a etapa como log
        self._registrar_etapa("Redução de Ruído", y, voz_limpa, t0)

        #---------------------------------------------------

        t0 = time.perf_counter()
        # Marca o início da etapa para registrar o tempo de processamento

        # Define os parâmetros do filtro:
        fs = 16000 # - fs: taxa de amostragem do áudio
        lowcut = 80 # - lowcut: frequência mínima permitida (remove graves excessivos)
        highcut = 7500 # - highcut: frequência máxima permitida (remove ruídos muito agudos)
        order = 5 # - order: ordem do filtro (define a "suavidade" da curva de corte)
        
        # Carrega novamente o áudio que será filtrado
        data, sr = sf.read(self.audio_sem_ruido)
        
        # Frequência de Nyquist (metade da taxa de amostragem), usada para normalizar frequências
        nyquist = 0.5 * fs
        
        # Normaliza as frequências de corte para o cálculo digital
        low = lowcut / nyquist
        high = highcut / nyquist
        
        # Cria um filtro digital Butterworth Passa-Banda
        b, a = butter(order, [low, high], btype='band')
        
        # Aplica o filtro ao sinal, removendo frequências fora da faixa definida
        y_filter = lfilter(b, a, data)
        
        sf.write(self.audio_filtro_aplicado, y_filter, sr)
        # Salva o áudio filtrado para uso na próxima etapa

        self._registrar_etapa("Filtro Passa-Banda", data, y_filter, t0)
        # Registra comparativo antes/depois, para análise de qualidade e tempo

        #--------------------------------------------------- 
        # Marca o início da etapa para medir o tempo de processamento
        t0 = time.perf_counter()
        
        # Carrega o áudio filtrado (etapa anterior), agora em formato manipulável pelo pydub
        audio = AudioSegment.from_wav(self.audio_filtro_aplicado)
        
        # Ajusta o ganho para que o pico máximo do áudio fique próximo de 0 dBFS (equaliza o volume geral)
        normalizado = audio.apply_gain(-audio.max_dBFS)
        
        # Aumenta levemente o volume para dar mais clareza à fala após a equalização
        normalizado = normalizado.apply_gain(+3)
        
        # Salva o áudio normalizado para uso na etapa de transcrição
        normalizado.export(self.audio_volume_normalizado, format="wav")
        
        # Carrega o áudio antes da normalização (para comparação visual/auditiva no log)
        y_pre, _ = librosa.load(self.audio_filtro_aplicado, sr=16000)

        # Carrega o áudio após a normalização
        y_pos, _ = librosa.load(self.audio_volume_normalizado, sr=16000)
        
        # Registra essa etapa, permitindo análise de diferença e tempo de processamento
        self._registrar_etapa("Normalização de Volume", y_pre, y_pos, t0)
       

        #---------------------------------------------------

        subprocess.run([
            "ffmpeg", "-y", "-i", self.audio_bruto,
            "-c:a", "libmp3lame", "-b:a", "128k",
            self.part_dir_audio
        ], check=True)

        self.close_data(self.audio_bruto)
        self.close_data(self.audio_mono)
        self.close_data(self.audio_sem_ruido)
        self.close_data(self.audio_filtro_aplicado)
        os.rename(self.audio_volume_normalizado, self.audio)
        
        self.audio_per_minute(60, tipo, resumo)
        return
    
    def audio_per_minute(self, times_second, tipo, resumo):
        result = []
        duracao_inicial = -times_second
        headers = {'Connection': 'keep-alive'}

        params = {
            "id_solicitation": self.instance_time,
            "status": "Gerando Audios Cortados"
        }
        query = urlencode(params)
        requests.get(f'https://{self.host}/status?{query}', headers=headers)

        for i in range(math.ceil(self.obter_duracao_audio()/times_second)):
            duracao_inicial += times_second
            self.cortar_audio(f'{self.instance_time}_{i+1}.wav', self.segundos_para_tempo(duracao_inicial), '00:01:00')
            result.append(os.path.join(self.audio_dir, f'{self.instance_time}_{i+1}.wav',))
        self.close_data(self.audio)

        result = ClassManageDecode(result, self.filename, self.pattern).transcrever_com_tempo(self.part_dir, tipo, self.host, self.instance_time, self.log_metricas)

        params = {
            "id_solicitation": self.instance_time,
            "status": "Finalizando..."
        }
        query = urlencode(params)
        requests.get(f'https://{self.host}/status?{query}', headers=headers)
        
        texts = ClassManageResume(result, self.part_dir, resumo)
        texts.gerar_json_file()
        texts.text_resume()

        return 
    
    def cortar_audio(self, output, start_time, duration="00:05:00"):
        command = [
            "ffmpeg", "-y",
            "-ss", start_time,
            "-i", self.audio,
            "-t", duration,
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            os.path.join(self.audio_dir, output)
        ]
        subprocess.run(command)
    
    def obter_duracao_audio(self):
        info = mediainfo(self.audio)
        duration = float(info['duration'])
        return duration
    
    def segundos_para_tempo(self, first_tempt):
        horas = first_tempt // 3600
        minutos = (first_tempt % 3600) // 60
        segundos_restantes = first_tempt % 60
        return f"{horas:02}:{minutos:02}:{segundos_restantes:02}"
    
    def close_data(self, data):
        os.remove(data)
    
    def _rms_db(self, y):
        rms = np.sqrt(np.mean(y**2) + 1e-12)
        return 20 * np.log10(rms + 1e-12)

    def _registrar_etapa(self, nome, y_pre, y_pos, inicio_tempo):
        tempo_exec = time.perf_counter() - inicio_tempo
        rms_pre = self._rms_db(y_pre)
        rms_pos = self._rms_db(y_pos)
        delta = rms_pos - rms_pre

        with open(self.log_metricas, "a", encoding="utf-8") as f:
            f.write(f"[{nome}]\n")
            f.write(f"RMS Antes: {rms_pre:.2f} dB\n")
            f.write(f"RMS Depois: {rms_pos:.2f} dB\n")
            f.write(f"ΔRMS: {delta:.2f} dB | Tempo: {tempo_exec:.3f}s\n\n")