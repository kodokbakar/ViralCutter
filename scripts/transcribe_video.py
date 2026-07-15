import os
import sys
import subprocess
import torch
import time
import gc
import re
from i18n.i18n import I18nAuto

i18n = I18nAuto()

def log_step(message):
    print(f"[TRANSCRIBE {time.strftime('%H:%M:%S')}] {message}", flush=True)


def log_gpu_state(label):
    if not torch.cuda.is_available():
        log_step(f"{label}: CUDA unavailable")
        return

    try:
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        log_step(
            f"{label}: GPU={torch.cuda.get_device_name(0)} "
            f"allocated={allocated:.2f}GB reserved={reserved:.2f}GB"
        )
    except Exception as e:
        log_step(f"{label}: failed to read torch CUDA memory: {e}")

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            log_step(f"{label}: nvidia-smi memory/util={result.stdout.strip()}")
    except Exception as e:
        log_step(f"{label}: nvidia-smi unavailable: {e}")


def get_audio_duration(input_file):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return None

        return float(result.stdout.strip())
    except Exception:
        return None


def get_env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default

def normalize_language(language):
    if language is None:
        return None

    language = str(language).strip()
    if not language or language.lower() == "auto":
        return None

    language = language.lower()

    aliases = {
        "zh-cn": "zh",
        "zh-tw": "zh",
        "chinese": "zh",
        "indonesian": "id",
        "english": "en",
        "portuguese": "pt",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "italian": "it",
        "japanese": "ja",
        "korean": "ko",
        "russian": "ru",
    }

    return aliases.get(language, language)

def apply_safe_globals_hack():
    """
    Workaround for 'Weights only load failed' error in newer PyTorch versions.
    We first try to add safe globals. If that's not enough/fails, we monkeypatch torch.load.
    """
    try:
        import omegaconf
        if hasattr(torch.serialization, 'add_safe_globals'):
            torch.serialization.add_safe_globals([
                omegaconf.listconfig.ListConfig,
                omegaconf.dictconfig.DictConfig,
                omegaconf.base.ContainerMetadata,
                omegaconf.base.Node
            ])
            print("Aplicado patch de segurança para globals do Omegaconf.")
            
        # Monkeypatch agressivo para garantir compatibilidade com Pyannote/WhisperX antigos
        original_load = torch.load
        
        def safe_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return original_load(*args, **kwargs)
            
        torch.load = safe_load
        print("Aplicado monkeypatch em torch.load para forçar weights_only=False.")
        
    except ImportError:
        pass
    except Exception as e:
        print(f"Aviso ao tentar aplicar patch de globals: {e}")

    try:
        import torchaudio
        if not hasattr(torchaudio, 'list_audio_backends'):
            torchaudio.list_audio_backends = lambda: []
            print("Aplicado monkeypatch em torchaudio.list_audio_backends para PyTorch >= 2.4.")
    except Exception as e:
        pass

def parse_srt(srt_path):
    """
    Parses an SRT file into a list of segments expected by WhisperX alignment.
    [{'start': float, 'end': float, 'text': str}, ...]
    """
    print(f"Parsing SRT: {srt_path}")
    segments = []
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = content.replace('\r\n', '\n')
        blocks = content.strip().split('\n\n')
        
        def time_to_seconds(t_str):
            # SRT: 00:00:00,000
            t_str = t_str.replace(',', '.')
            parts = t_str.split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
            return 0.0

        for block in blocks:
            lines = block.split('\n')
            # Busca linha de tempo
            for i, line in enumerate(lines):
                if '-->' in line:
                    start_str, end_str = line.split(' --> ')
                    text_lines = lines[i+1:]
                    text = " ".join(text_lines).strip()
                    text = re.sub(r'<[^>]+>', '', text) # Remove tags
                    
                    if text:
                        start = time_to_seconds(start_str.strip())
                        end = time_to_seconds(end_str.strip())
                        segments.append({
                            "start": start,
                            "end": end,
                            "text": text
                        })
                    break
    except Exception as e:
        print(f"Error parsing SRT {srt_path}: {e}")
        return None
    return segments

def parse_vtt(vtt_path):
    """
    Parses a VTT file (WebVTT) into valid segments for WhisperX.
    """
    print(f"Parsing VTT: {vtt_path}")
    segments = []
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        def vtt_time_to_seconds(t_str):
            # VTT: 00:00:00.000 or 00:00.000
            t_str = t_str.strip()
            parts = t_str.split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
            return 0.0

        current_entry = {"text": []}
        
        for line in lines:
            line = line.strip()
            if not line:
                # Fim de bloco, salva se tiver tempo e texto
                if "start" in current_entry and current_entry["text"]:
                    full_text = " ".join(current_entry["text"]).strip()
                    # Limpeza extra VTT
                    full_text = re.sub(r'<[^>]+>', '', full_text)
                    full_text = re.sub(r'&[^;]+;', '', full_text)
                    
                    if full_text:
                        segments.append({
                            "start": current_entry["start"],
                            "end": current_entry["end"],
                            "text": full_text
                        })
                current_entry = {"text": []}
                continue
            
            if line.startswith("WEBVTT") or line.startswith("X-TIMESTAMP-MAP") or line.startswith("NOTE"):
                continue

            # Timestamp line: 00:00:05.000 --> 00:00:10.000 (pode ter settings depois)
            if "-->" in line:
                times = line.split("-->")
                start_str = times[0].strip()
                end_str = times[1].strip().split(" ")[0] # remove settings
                current_entry["start"] = vtt_time_to_seconds(start_str)
                current_entry["end"] = vtt_time_to_seconds(end_str)
            else:
                # É texto (se já tivermos timestamps)
                if "start" in current_entry:
                     current_entry["text"].append(line)
                     
        # Salva ultimo bloco se existir
        if "start" in current_entry and current_entry["text"]:
            full_text = " ".join(current_entry["text"]).strip()
            full_text = re.sub(r'<[^>]+>', '', full_text)
            if full_text:
                segments.append({
                    "start": current_entry["start"],
                    "end": current_entry["end"],
                    "text": full_text
                })

    except Exception as e:
        print(f"Error parsing VTT {vtt_path}: {e}")
        return None
    return segments

def transcribe(input_file, model_name='large-v3', project_folder='tmp', language='auto'):
    start_time = time.time()

    log_step(i18n(f"Iniciando transcrição de {input_file}..."))
    log_step(f"Python: {sys.executable}")
    log_step(f"Torch: {torch.__version__}")
    log_step(f"CUDA available: {torch.cuda.is_available()}")
    log_step(f"CUDA version: {torch.version.cuda}")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input video not found: {input_file}")

    input_size_mb = os.path.getsize(input_file) / 1024**2
    input_duration = get_audio_duration(input_file)
    duration_text = f"{input_duration:.1f}s" if input_duration else "unknown"

    log_step(f"Input size: {input_size_mb:.2f} MB")
    log_step(f"Input duration: {duration_text}")
    
    if project_folder is None:
        project_folder = os.path.dirname(input_file)
        if not project_folder:
            project_folder = 'tmp'

    output_folder = project_folder
    os.makedirs(output_folder, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    srt_file = os.path.join(output_folder, f"{base_name}.srt")
    tsv_file = os.path.join(output_folder, f"{base_name}.tsv")
    json_file = os.path.join(output_folder, f"{base_name}.json")

    # Verifica se os arquivos já existem
    if os.path.exists(srt_file) and os.path.exists(tsv_file) and os.path.exists(json_file):
        print(f"Os arquivos SRT, TSV e JSON já existem. Pulando a transcrição.")
        return srt_file, tsv_file

    # Device Setup
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = os.environ.get("VIRALCUTTER_WHISPER_COMPUTE_TYPE")
    if not compute_type:
        compute_type = "float16" if device == "cuda" else "int8"

    batch_size = get_env_int("VIRALCUTTER_WHISPER_BATCH_SIZE", 8 if device == "cuda" else 4)
    chunk_size = get_env_int("VIRALCUTTER_WHISPER_CHUNK_SIZE", 10)

    log_step(f"Using device: {device}")
    log_step(f"Using compute_type: {compute_type}")
    log_step(f"Using batch_size: {batch_size}")
    log_step(f"Using chunk_size: {chunk_size}")
    selected_language = normalize_language(language)
    language_mode = selected_language or "auto"
    log_step(f"Whisper language mode: {language_mode}")

    if device == "cuda":
        log_gpu_state("before whisperx import")

    try:
        apply_safe_globals_hack()

        log_step("Importing whisperx...")
        import whisperx
        log_step("whisperx import OK")

        if device == "cuda":
            log_gpu_state("after whisperx import")
        
        # 1. Carregar Áudio (sempre necessário)
        log_step(f"Loading audio: {input_file}")
        audio_load_start = time.time()
        audio = whisperx.load_audio(input_file)
        log_step(f"Audio loaded in {time.time() - audio_load_start:.2f}s")
        
        # 2. Verificar se existem legendas baixadas para Alignment Only
        # Procurar por *.srt E *.vtt na pasta que comecem com input (ou o nome base)
        if os.path.exists(os.path.join(output_folder, "input.srt")):
            potential_subs = [os.path.join(output_folder, "input.srt")]
        elif os.path.exists(os.path.join(output_folder, "input.vtt")):
            potential_subs = [os.path.join(output_folder, "input.vtt")]
        else:
            potential_subs = []
        
        start_segments = None
        alignment_only = False
        
        # Alignment-only mode has no ASR language detection, so use selected language or EN fallback.
        detected_language = selected_language or "en"

        if potential_subs:
            sub_path = potential_subs[0]
            print(f"Usando legenda fornecida: {sub_path}")
            
            if sub_path.endswith('.srt'):
                parsed = parse_srt(sub_path)
            elif sub_path.endswith('.vtt'):
                parsed = parse_vtt(sub_path)
            else:
                parsed = None

            if parsed and len(parsed) > 0:
                start_segments = parsed
                alignment_only = True
                
                # force selected language for alignment, but detected_language is used for model loading
                detected_language = selected_language or "en"
                log_step(f"Subtitle alignment language: {detected_language}")
                
                print("--- MODO ALINHAMENTO RÁPIDO ATIVADO ---")
        
        result = None
        
        if alignment_only and start_segments:
            # Pular Transcrição, ir direto para Alinhamento
            print("--- MODO ALINHAMENTO RÁPIDO ATIVADO ---")
            # Estrutura que o align espera: {'segments': [...], 'language': ...}
            # Mas o align recebe segments como lista.
            pass 
        else:
            # 3. Transcrever (Caminho Normal)
            log_step("No valid subtitles found. Starting full WhisperX transcription.")
            log_step(f"Loading WhisperX model: {model_name}")

            model_load_start = time.time()
            model = whisperx.load_model(
                model_name,
                device,
                compute_type=compute_type,
                language=selected_language,
                asr_options={"hotwords": None},
            )
            log_step(f"WhisperX model loaded in {time.time() - model_load_start:.2f}s")

            if device == "cuda":
                log_gpu_state("after whisperx.load_model")

            log_step("Starting model.transcribe()")
            transcribe_start = time.time()
            result = model.transcribe(
                audio,
                batch_size=batch_size,
                chunk_size=chunk_size,
            )
            log_step(f"model.transcribe() completed in {time.time() - transcribe_start:.2f}s")

            if device == "cuda":
                log_gpu_state("after model.transcribe")

            detected_language = selected_language or result["language"]
            start_segments = result["segments"]

            log_step(f"Detected language: {detected_language}")
            log_step(f"Transcribed segments: {len(start_segments)}")
            
            # Limpar modelo de transcrição
            if device == "cuda":
                del model
                gc.collect()
                torch.cuda.empty_cache()
                log_gpu_state("after transcription model cleanup")

        # 4. Alinhar (Sempre executado, seja com subs parsed ou transcritos)
        log_step(f"Starting alignment for language: {detected_language}")
        # Usa o modelo específico solicitado pelo usuário: WAV2VEC2_ASR_LARGE_LV60K_960H
        # Mas o whisperx.load_align_model escolhe automaticamente baseado na linguagem.
        # Se for inglês, ele usa wav2vec2-large-960h-lv60-self geralmente.
        # Não podemos forçar facilmente o modelo exato sem hackear o whisperx, mas o padrão é bom.
        
        try:
            align_load_start = time.time()
            model_a, metadata = whisperx.load_align_model(language_code=detected_language, device=device)
            log_step(f"Alignment model loaded in {time.time() - align_load_start:.2f}s")

            if device == "cuda":
                log_gpu_state("after load_align_model")

            align_start = time.time()
            aligned_result = whisperx.align(
                start_segments,
                model_a,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
            log_step(f"whisperx.align() completed in {time.time() - align_start:.2f}s")
            
            # aligned_result agora contém "segments" com word timestamps
            result = aligned_result
            result["language"] = detected_language
            
            if device == "cuda":
                del model_a
                torch.cuda.empty_cache()
                log_gpu_state("after alignment model cleanup")
                 
        except Exception as e:
            print(f"Erro durante alinhamento: {e}. ")
            if alignment_only:
                 print("Falha crítica no alinhamento de legendas externas. Abortando usage de legendas externas.")
                 # Opcional: Fallback para transcrição normal se falhar? Seria complexo aqui pois já limpamos memória.
                 # Vamos apenas salvar o que temos (timestamps da legenda original podem não bater com áudio perfeitamente se não alinhar)
                 result = {"segments": start_segments, "language": detected_language}
            else:
                 print("Continuando com transcrição bruta.")

        # 5. Salvar Resultados
        log_step("Saving transcription outputs...")
        from whisperx.utils import get_writer
        
        save_options = {
            "highlight_words": False,
            "max_line_count": None,
            "max_line_width": None
        }
        
        # Se veio do alignment_only, result é {'segments': [...], ...}
        # Se o alinhamento falhou, result tem segments originais.
        
        # WhisperX writers esperam um dicionário result com chaves 'segments', 'language'.
        
        writer_srt = get_writer("srt", output_folder)
        writer_srt(result, input_file, save_options)
        
        writer_tsv = get_writer("tsv", output_folder)
        writer_tsv(result, input_file, save_options)
        
        writer_json = get_writer("json", output_folder)
        writer_json(result, input_file, save_options)
        
        end_time = time.time()
        elapsed = end_time - start_time
        log_step(f"Transcription completed in {int(elapsed//60)}m {int(elapsed%60)}s.")

    except Exception as e:
        log_step(f"CRITICAL transcription error: {e}")
        import traceback
        traceback.print_exc()
        raise

    if not os.path.exists(srt_file):
        print(f"AVISO: Arquivo SRT {srt_file} não encontrado após execução.")
    
    return srt_file, tsv_file
