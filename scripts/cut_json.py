import json
import os
from typing import List, Tuple, Optional, Any

def process_segments(data, start_time, end_time, segments_to_splice=None):
    if segments_to_splice:
        valid_slices = []
        for s in segments_to_splice:
            try:
                s_start, s_end = float(s[0]), float(s[1])
                if s_end > s_start:
                    valid_slices.append((s_start, s_end))
            except (ValueError, TypeError, IndexError):
                continue

        if valid_slices:
            new_segments = []
            cum_offset = 0.0
            for slice_start, slice_end in valid_slices:
                slice_dur = slice_end - slice_start
                for segment in data.get('segments', []):
                    seg_start = float(segment.get('start', 0.0))
                    seg_end = float(segment.get('end', 0.0))

                    if seg_end <= slice_start or seg_start >= slice_end:
                        continue

                    new_seg_start = cum_offset + max(0.0, seg_start - slice_start)
                    new_seg_end = cum_offset + min(slice_dur, seg_end - slice_start)

                    new_words = []
                    if 'words' in segment:
                        for word in segment['words']:
                            w_start = float(word.get('start', 0.0))
                            w_end = float(word.get('end', 0.0))
                            if w_end > slice_start and w_start < slice_end:
                                new_w_start = cum_offset + max(0.0, w_start - slice_start)
                                new_w_end = cum_offset + min(slice_dur, w_end - slice_start)
                                word_copy = word.copy()
                                word_copy['start'] = round(new_w_start, 3)
                                word_copy['end'] = round(new_w_end, 3)
                                new_words.append(word_copy)

                    if 'words' in segment:
                        if new_words:
                            new_segment = segment.copy()
                            new_segment['start'] = round(new_seg_start, 3)
                            new_segment['end'] = round(new_seg_end, 3)
                            new_segment['words'] = new_words
                            new_segment['text'] = " ".join(str(w.get('word', '')).strip() for w in new_words).strip()
                            new_segments.append(new_segment)
                    else:
                        if new_seg_end > new_seg_start:
                            new_segment = segment.copy()
                            new_segment['start'] = round(new_seg_start, 3)
                            new_segment['end'] = round(new_seg_end, 3)
                            new_segments.append(new_segment)

                cum_offset += slice_dur

            return {'segments': new_segments}

    new_segments = []
    
    for segment in data.get('segments', []):
        seg_start = segment.get('start', 0)
        seg_end = segment.get('end', 0)
        
        # Verifica interseção
        if seg_end <= start_time or seg_start >= end_time:
            continue
            
        # Calcula overlap
        # Ajusta timestamps relativos ao corte
        new_seg_start = max(0, seg_start - start_time)
        new_seg_end = min(end_time, seg_end) - start_time
        
        # Filtra palavras se existirem
        new_words = []
        if 'words' in segment:
            for word in segment['words']:
                w_start = word.get('start', 0)
                w_end = word.get('end', 0)
                
                if w_end > start_time and w_start < end_time:
                    new_w_start = max(0, w_start - start_time)
                    new_w_end = min(end_time, w_end) - start_time
                    word_copy = word.copy()
                    word_copy['start'] = new_w_start
                    word_copy['end'] = new_w_end
                    new_words.append(word_copy)
        
        # Se sobraram palavras ou se o segmento é válido no tempo
        if new_words or (new_seg_end > new_seg_start):
            new_segment = segment.copy()
            new_segment['start'] = new_seg_start
            new_segment['end'] = new_seg_end
            if 'words' in segment:
                new_segment['words'] = new_words
            new_segments.append(new_segment)
            
    return {'segments': new_segments}

def cut_json_transcript(input_json_path, output_json_path, start_time, end_time, hook_title=None, title=None, segments_to_splice=None):
    """
    Lê o input.json (WhisperX), recorta o trecho e salva em output_json_path com timestamps ajustados.
    """
    if not os.path.exists(input_json_path):
        print(f"Aviso: {input_json_path} não encontrado. Não foi possível gerar JSON do corte.")
        return

    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        new_data: dict = dict(process_segments(data, start_time, end_time, segments_to_splice=segments_to_splice))
        if hook_title:
            new_data['hook_title'] = str(hook_title).strip().upper()
        if title:
            new_data['title'] = str(title).strip()
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
            
        print(f"JSON de legenda gerado: {output_json_path}")
        
    except Exception as e:
        print(f"Erro ao cortar JSON: {e}")
