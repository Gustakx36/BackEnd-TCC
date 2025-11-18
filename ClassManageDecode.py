from huggingface_hub import snapshot_download
from ClassManagePart import ClassManagePart
from faster_whisper import WhisperModel
from urllib.parse import urlencode
import requests
import time
import os

local_dir = snapshot_download("Systran/faster-whisper-large-v3")

class ClassManageDecode:
    def __init__(self, my_audios, filename, pattern):
        self.my_audios = my_audios
        self.filename = filename
        self.pattern = pattern

    def transcrever_com_tempo(self, part_dir, tipo, host, id_solicitacao, log_metricas):
        headers = {'Connection': 'keep-alive'}
        params = {
            "id_solicitation": id_solicitacao,
            "status": "Carregando Modelo"
        }
        query = urlencode(params)
        requests.get(f'https://{host}/status?{query}', headers=headers)
        model = WhisperModel(local_dir, device="cuda", compute_type="float16")
        index_transcricao = 0
        returner = []
        index_scene = 0
        tempo_total_trancricao = 0
        tempo_total_geracao_trecho = 0
        for audio in self.my_audios:
            requests.get(f'http://{host}/paginas?id_solicitation={id_solicitacao}', headers=headers)

            t0 = time.perf_counter()
            segments, info = model.transcribe(
                audio,
                word_timestamps=True,
                language="pt",
                task="transcribe",
                temperature=0,
                beam_size=8,
                vad_filter=False
            )

            t1 = time.perf_counter()
            tempo_transcricao = t1 - t0

            tempo_total_trancricao += tempo_transcricao

            result = list(segments)
            dump = [seg._asdict() for seg in result]  
            returner.extend(dump)

            with open(log_metricas, "a", encoding="utf-8") as f:
                f.write("-"*10 + "\n\n")
                f.write(f"[Transcrição {index_transcricao}]\n")
                f.write(f"Áudio: {os.path.basename(audio)}\n")
                f.write(f"Tempo Transcrição: {tempo_transcricao:.2f}s\n\n")

            t0 = time.perf_counter()
            new_index = ClassManagePart(self.pattern, self.filename, part_dir).salvar_resultado_em_trecho(index_scene, result, index_transcricao, log_metricas, tipo)
            t1 = time.perf_counter()

            tempo_geracao_trecho = t1 - t0

            tempo_total_geracao_trecho += tempo_geracao_trecho

            index_scene = new_index
            self.close_data(audio)

            
            index_transcricao += 1
        with open(log_metricas, "a", encoding="utf-8") as f:
            f.write("-"*10 + "\n\n")
            f.write(f"[Tempo Total da Solicitação({id_solicitacao})]\n")
            f.write(f"Tempo Total de Processamento (Transcrição + Geração de Trecho): {(tempo_total_trancricao+tempo_total_geracao_trecho):.2f}s\n\n")
            f.write(f"Tempo Total de Transcrição: {tempo_total_trancricao:.2f}s\n\n")
            f.write(f"Tempo Total de Geração de Trecho: {tempo_total_geracao_trecho:.2f}s\n\n")
        return returner
    
    def close_data(self, audio):
        os.remove(audio)