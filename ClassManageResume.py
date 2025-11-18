from openai import OpenAI
import json
import os

class ClassManageResume:
    def __init__(self, result, caminho, resumo = False):
        self.caminho = caminho
        self.result = result
        self.fazer_resumo = resumo
        os.makedirs(f"{self.caminho}/json", exist_ok=True)
        os.makedirs(f"{self.caminho}/txt", exist_ok=True)

    def text_resume(self):
        if not self.fazer_resumo:
            return
        texto_transcrito = "\n".join([scene['text'] for scene in self.result])
        client = OpenAI()

        resp = client.responses.create(
            model="gpt-5-nano-2025-08-07",
            input=f"""
        Você é uma ótima ferramenta para resumos.
        Resuma o texto abaixo em poucas frases, de forma clara e objetiva.
        Não inclua introduções como "claro, aqui está o resumo" ou "o resumo é".
        Mostre apenas o resumo final, direto e bem escrito.

        Texto:
        {texto_transcrito}
        """
        )

        with open(f"{self.caminho}/txt/texto_resumo.txt", "a", encoding="utf-8") as f:
            f.write(f"{resp.output[1].content[0].text}")
    
    def gerar_json_file(self):
        with open(f"{self.caminho}/json/json.json", "w", encoding="utf-8") as f:
            json.dump(self.result, f, ensure_ascii=False, indent=4)