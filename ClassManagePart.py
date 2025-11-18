import re, unicodedata
import subprocess
import jellyfish
import time
import math
import os

class ClassManagePart:
    def __init__(self, pattern, filename, part_dir):
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.part_dir = part_dir
        self.pattern = self.normalizar(pattern)
        self.pattern_metaphone = jellyfish.metaphone(self.pattern)
        self.filename = filename
    
    def normalizar(self, txt):
        txt = unicodedata.normalize("NFD", txt)
        txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
        return txt.lower()
    
    def valida_regex(self, palavra):
        return re.search(rf"\b{self.pattern}\b", self.normalizar(palavra), re.IGNORECASE)

    def valida_fonetica(self, palavra):
        return jellyfish.metaphone(palavra.strip().replace(",", "").replace(".", "")) == self.pattern_metaphone

    def salvar_resultado_em_trecho(self, index_scene, result, index_transcricao, log_metricas,tipo = 1):
        if len(result) <= 0:
            return index_scene
        tempo_total = result[-1].end

        for scene in result:
        # Percorre cada trecho (scene) da transcrição gerada pelo modelo

            palavras_encontradas = []

            # Cria uma lista com todas as palavras dentro do trecho que correspondem ao padrão (regex)
            if tipo == 1:
                palavras_encontradas = [
                    w for w in scene.words
                    if self.valida_regex(w.word)
                ]
            # Cria uma lista com todas as palavras dentro do trecho que correspondem ao padrão (jellyfish)
            elif tipo == 2:
                palavras_encontradas = [
                    w for w in scene.words
                    if self.valida_fonetica(w.word)
                ]
            else:
                index_scene += 1
                return
            
            if not palavras_encontradas:
                index_scene += 1
                return

            primeira = palavras_encontradas[0]  # Primeira ocorrência da palavra
            ultima = palavras_encontradas[-1]   # Última ocorrência da palavra

            inicio = max(primeira.start - 1.5, 0) + (index_transcricao * 60)
            fim = min(ultima.end + 1.5, tempo_total) + (index_transcricao * 60)
            # Define o início e o fim do corte com margem de 1.5s antes e depois

            start_time = self.segundos_para_tempo(inicio)
            duration = self.segundos_para_tempo(fim - inicio)
            # Converte o tempo em segundos para formato hh:mm:ss usado pelo FFmpeg

            probabilidade = max(primeira.probability, ultima.probability)
            # Define a maior probabilidade de reconhecimento entre as duas palavras

            file_output = f'id({round(time.time())}_{index_scene}_{scene.id})_prob({probabilidade:.2f}).mp4'
            # Gera o nome do arquivo de saída com ID, índice e probabilidade

            t0 = time.perf_counter()
            self.cut_part(file_output, start_time, duration)
            t1 = time.perf_counter()
            # Realiza o corte do vídeo com base nos tempos calculados e mede o tempo gasto

            tempo_geracao = t1 - t0  # Calcula o tempo de geração do trecho

            with open(log_metricas, "a", encoding="utf-8") as f:
                # Registra no log informações sobre o trecho gerado
                f.write(f"[Geração de Trecho ID({scene.id})]\n")
                f.write(f"Tempo de Geração de Trecho: {tempo_geracao:.2f}s\n")
                f.write(f"Texto: {scene.text}\n")
                f.write(f"Padrão: {self.pattern}\n\n")

        index_scene += 1  # Avança para a próxima cena
        return index_scene  # Retorna o número total de trechos processados

    def cut_part(self, file_output, start_time, duration="00:05:00"):
        tempo = round(time.time())
        temp_output_video = self.temp_dir = os.path.join(self.app_dir, f'Trechos/temp/{tempo}_{file_output}')
        final_output_video = os.path.join(self.part_dir, file_output)
        command = [
            "ffmpeg",
            "-y",
            "-ss", start_time,
            "-i", self.filename,
            "-t", duration,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "26",
            "-vf", "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2",
            "-c:a", "aac",
            "-b:a", "48k",
            "-movflags", "+faststart",
            temp_output_video
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate()
        os.rename(temp_output_video, final_output_video)
    
    def segundos_para_tempo(self, tempo_segundos):
        horas = int(tempo_segundos // 3600)
        minutos = int((tempo_segundos % 3600) // 60)
        segundos = int(tempo_segundos % 60)
        milissegundos = int((tempo_segundos % 1) * 1000)

        return f"{horas:02}:{minutos:02}:{segundos:02}.{milissegundos:03}"

    def close_data(self, audio):
        os.remove(audio)