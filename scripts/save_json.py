import os
import json

def ensure_default_order(segments_data):
    if isinstance(segments_data, dict) and isinstance(segments_data.get("segments"), list):
        for index, segment in enumerate(segments_data["segments"], start=1):
            if isinstance(segment, dict) and "order" not in segment:
                segment["order"] = index
    return segments_data

def save_viral_segments(segments_data=None, project_folder="tmp"):
    output_txt_file = os.path.join(project_folder, "viral_segments.txt")
    output_json_file = os.path.join(project_folder, "viral_segments.json")

    if segments_data is not None:
        with open(output_txt_file, 'w', encoding='utf-8') as file:
            segments_data = ensure_default_order(segments_data)
            json.dump(segments_data, file, ensure_ascii=False, indent=4)
        with open(output_json_file, 'w', encoding='utf-8') as file:
            json.dump(segments_data, file, ensure_ascii=False, indent=4)
        print(f"Segmentos virais salvos em {output_txt_file}\n")
        return

    if not os.path.exists(output_txt_file):
        while True:
            user_input = input("\nPor favor, insira o JSON no formato desejado:\n")
            try:
                segments_data = json.loads(user_input)
                if "segments" in segments_data and isinstance(segments_data["segments"], list):
                    with open(output_txt_file, 'w', encoding='utf-8') as file:
                        segments_data = ensure_default_order(segments_data)
                        json.dump(segments_data, file, ensure_ascii=False, indent=4)
                    with open(output_json_file, 'w', encoding='utf-8') as file:
                        json.dump(segments_data, file, ensure_ascii=False, indent=4)
                    print(f"Segmentos virais salvos em {output_txt_file}")
                    break
                else:
                    print("Formato inválido. Certifique-se de que a estrutura está correta.")
            except json.JSONDecodeError:
                print("Erro ao decifrar o JSON. Por favor, verifique a formatação.")
            print("Por favor, tente novamente.")
    else:
        print(f"O arquivo {output_txt_file} já existe. Nenhuma entrada adicional é necessária.")