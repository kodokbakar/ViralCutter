import os
import re
import subprocess
import sys

import yt_dlp

from i18n.i18n import I18nAuto
i18n = I18nAuto()

def sanitize_filename(name):
    """Remove caracteres inválidos e emojis para evitar erro de encoding no Windows."""
    # Remove caracteres reservados do sistema de arquivos
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    
    # Remove emojis e caracteres não suportados pelo console Windows (CP1252)
    # Isso mantém acentos (á, ç, é) mas remove 😱, etc.
    try:
        cleaned = cleaned.encode('cp1252', 'ignore').decode('cp1252')
    except:
        # Fallback se não tiver CP1252: remove tudo não-ascii (remove acentos)
        cleaned = cleaned.encode('ascii', 'ignore').decode('ascii')
        
    cleaned = cleaned.strip()
    return cleaned

def progress_hook(d):
    if d['status'] == 'downloading':
        try:
            p = d.get('_percent_str', '').replace('%','')
            print(f"[download] {p}% - {d.get('_eta_str', 'N/A')} remaining", flush=True)
        except:
            pass
    elif d['status'] == 'finished':
        print(f"[download] Download concluído: {d['filename']}", flush=True)

def extract_gdrive_id(url):
    """Extract file ID from supported Google Drive file URLs."""
    patterns = [
        r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/uc\?export=download&id=([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def is_gdrive_url(url):
    return "drive.google.com" in url or extract_gdrive_id(url) is not None


def validate_gdrive_url(url):
    if "drive.google.com/drive/folders/" in url:
        raise ValueError(i18n("Folder link detected. Please share an individual Google Drive file link."))

    file_id = extract_gdrive_id(url)
    if not file_id:
        raise ValueError(i18n("Invalid Google Drive URL format."))

    return file_id


def remove_partial_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def looks_like_drive_error_page(path):
    try:
        with open(path, "rb") as f:
            head = f.read(4096).lower()
        return b"<html" in head and (b"google" in head or b"drive" in head)
    except OSError:
        return False


def is_video_file(path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return result.returncode == 0 and "video" in result.stdout.lower()
    except OSError:
        return False


def download_from_gdrive(url, base_root="VIRALS"):
    file_id = validate_gdrive_url(url)

    project_folder = os.path.join(base_root, f"gdrive_{file_id[:8]}")
    os.makedirs(project_folder, exist_ok=True)

    output_path = os.path.join(project_folder, "input.mp4")

    if os.path.exists(output_path):
        if (
            os.path.getsize(output_path) > 1024
            and not looks_like_drive_error_page(output_path)
            and is_video_file(output_path)
        ):
            print(i18n("Video already exists at: {}").format(output_path))
            print(i18n("Skipping download and reusing local file."))
            return output_path, project_folder

        print(i18n("Existing file found but seems corrupted/empty. Downloading again..."))
        remove_partial_file(output_path)

    print(i18n("Downloading from Google Drive..."))
    print(i18n("File ID: {}").format(file_id))

    try:
        import gdown

        drive_url = f"https://drive.google.com/uc?id={file_id}"
        result = gdown.download(drive_url, output_path, quiet=False)

        if not result or not os.path.exists(output_path) or os.path.getsize(output_path) <= 1024:
            remove_partial_file(output_path)
            raise RuntimeError(i18n("Downloaded file is empty or missing."))

        if looks_like_drive_error_page(output_path):
            remove_partial_file(output_path)
            raise RuntimeError(
                i18n("File not accessible. Set sharing to 'Anyone with the link'.")
            )

        if not is_video_file(output_path):
            remove_partial_file(output_path)
            raise RuntimeError(i18n("Downloaded file is not a video."))

        print(i18n("Download complete: {}").format(output_path))
        return output_path, project_folder

    except (ConnectionError, TimeoutError) as e:
        remove_partial_file(output_path)
        raise RuntimeError(i18n("Network error while downloading from Google Drive. Please retry. Error: {}").format(e))
    except FileNotFoundError as e:
        remove_partial_file(output_path)
        raise RuntimeError(i18n("File not accessible. Set sharing to 'Anyone with the link'. Error: {}").format(e))
    except Exception as e:
        remove_partial_file(output_path)
        raise RuntimeError(i18n("Google Drive download failed. Set sharing to 'Anyone with the link'. Error: {}").format(e))

def download_from_gdrive_file_id(file_id, file_name=None, base_root="VIRALS"):
    from scripts import gdrive_client

    return gdrive_client.download_drive_video(
        file_id=file_id,
        file_name=file_name,
        base_root=base_root,
    )

def download(url, base_root="VIRALS", download_subs=True, quality="best"):
    if is_gdrive_url(url):
        return download_from_gdrive(url, base_root=base_root)

    # 1. Extrair informações do vídeo para pegar o título
    # 1. Extrair informações do vídeo para pegar o título
    print(i18n("Extracting video information..."))
    title = None
    
    # ... (Keep existing title extraction logic) ...
    # Instead of repeating it effectively, I will rely on the diff to keep it or re-write it if I have to replace the whole block.
    # Since replace_file_content works on line ranges, I should be careful.
    # Let's assume I'm replacing the whole function body or significant parts.
    
    # Tentativa 1: Com cookies
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'cookiesfrombrowser': ('chrome',)}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title')
    except Exception as e:
        try:
            print(i18n("Warning: Failed to extract info with cookies: {}").format(e))
        except UnicodeEncodeError:
            print(i18n("Warning: Failed to extract info with cookies: [Encoding Error in Message]"))

    # Tentativa 2: Sem cookies
    if not title:
        try:
             with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title')
        except Exception as e:
            try:
                print(i18n("Error getting video info (without cookies): {}").format(e))
            except UnicodeEncodeError:
                print(i18n("Error getting video info (without cookies): [Encoding Error in Message]"))

    # Fallback final
    if title:
        safe_title = sanitize_filename(title)
        try:
            print(i18n("Detected title: {}").format(title))
        except UnicodeEncodeError:
            # Fallback for Windows consoles that choke on Emojis
            clean_title = title.encode('ascii', 'replace').decode('ascii')
            print(i18n("Detected title: {}").format(clean_title))
    else:
        print(i18n("WARNING: Title could not be obtained. Using 'Unknown_Video'."))
        safe_title = i18n("Unknown_Video")

    # 2. Criar estrutura de pastas
    project_folder = os.path.join(base_root, safe_title)
    os.makedirs(project_folder, exist_ok=True)
    
    # Caminho final do vídeo
    output_filename = 'input' 
    output_path_base = os.path.join(project_folder, output_filename)
    final_video_path = f"{output_path_base}.mp4"

    # Verificação inteligente
    if os.path.exists(final_video_path):
        if os.path.getsize(final_video_path) > 1024: 
            try:
                print(i18n("Video already exists at: {}").format(final_video_path))
            except UnicodeEncodeError:
                print(i18n("Video already exists at: {}").format(final_video_path.encode('ascii', 'replace').decode('ascii')))
            print(i18n("Skipping download and reusing local file."))
            return final_video_path, project_folder
        else:
            print(i18n("Existing file found but seems corrupted/empty. Downloading again..."))
            try:
                os.remove(final_video_path)
            except:
                pass

    # Limpeza de temp
    temp_path = f"{output_path_base}.temp.mp4"
    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except:
            pass

    # Mapeamento de Qualidade
    quality_map = {
        "best": 'bestvideo+bestaudio/best',
        "1080p": 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        "720p": 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        "480p": 'bestvideo[height<=480]+bestaudio/best[height<=480]'
    }
    selected_format = quality_map.get(quality, 'bestvideo+bestaudio/best')
    print(i18n("Configuring download quality: {} -> {}").format(quality, selected_format))

    ydl_opts = {
        'format': selected_format,
        'overwrites': True,
        'outtmpl': output_path_base, 
        'postprocessor_args': [
            '-movflags', 'faststart'
        ],
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
        # Opções de Legenda
        'writesubtitles': download_subs,
        'writeautomaticsub': download_subs,
        'subtitleslangs': ['pt.*', 'en.*', 'sp.*'], # Prioritize generic PT, EN, SP
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'skip_download': False,
        'quiet': False,
        'no_warnings': False,
        'force_ipv4': True,
    }
    

    
    if download_subs:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegSubtitlesConvertor',
            'format': 'srt',
        }]

    try:
        print(i18n("Downloading video to: {}...").format(project_folder))
    except UnicodeEncodeError:
        print(i18n("Downloading video to: {}...").format(project_folder.encode('ascii', 'replace').decode('ascii')))
    
    # Tentativa 1: Com configuração original
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e)
        if "No address associated with hostname" in error_str or "Failed to resolve" in error_str:
            print(i18n("\n[CRITICAL ERROR] Connection Failure: Could not access YouTube."))
            print(i18n("Check your internet connection or if there is any DNS block."))
            print(i18n("Details: {}").format(e))
            sys.exit(1)
        
        elif download_subs and ("Unable to download video subtitles" in error_str or "429" in error_str):
            print(i18n("\nWarning: Error downloading subtitles ({}).").format(e))
            print(i18n("Retrying ONLY the video (without subtitles)..."))
            
            ydl_opts['writesubtitles'] = False
            ydl_opts['writeautomaticsub'] = False
            ydl_opts['postprocessors'] = [p for p in ydl_opts.get('postprocessors', []) if 'Subtitle' not in p.get('key', '')]
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e2:
                print(i18n("Fatal error on second attempt: {}").format(e2))
                raise
        elif "is not a valid URL" in error_str:
             print(i18n("Error: the entered link is not valid."))
             raise 
        else:
            print(i18n("Download error: {}").format(e))
            raise
    except Exception as e:
        print(i18n("Unexpected error: {}").format(e))
        raise

    # RENOMEAR LEGENDA PARA PADRÃO (input.vtt ou input.srt)
    # Se for VTT, converte para SRT para garantir compatibilidade.
    try:
        import glob
        # Pega a primeira que encontrar
        potential_subs = glob.glob(os.path.join(project_folder, "input.*.vtt")) + glob.glob(os.path.join(project_folder, "input.*.srt"))
        
        if potential_subs:
            best_sub = potential_subs[0]
            ext = os.path.splitext(best_sub)[1]
            new_name = os.path.join(project_folder, "input.srt") # Vamos padronizar tudo para .srt
            
            if ext.lower() == '.vtt':
                try:
                    print(i18n("Formatting complex VTT subtitle ({}) to clean SRT...").format(os.path.basename(best_sub)))
                except UnicodeEncodeError:
                    print(i18n("Formatting complex VTT subtitle ({}) to clean SRT...").format(os.path.basename(best_sub).encode('ascii', 'replace').decode('ascii')))
                try:
                    with open(best_sub, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    srt_content = []
                    counter = 1
                    
                    seen_texts = set()
                    last_text = ""
                    
                    for line in lines:
                        clean_line = line.strip()
                        # Ignora Headers e Metadados do VTT/Youtube
                        if clean_line.startswith("WEBVTT") or \
                           clean_line.startswith("X-TIMESTAMP") or \
                           clean_line.startswith("NOTE") or \
                           clean_line.startswith("Kind:") or \
                           clean_line.startswith("Language:"):
                            continue
                        
                        if "-->" in clean_line:
                            # Parse Timestamp
                            parts = clean_line.split("-->")
                            start = parts[0].strip()
                            # Remove tags de posicionamento "align:start position:0%"
                            end = parts[1].strip().split(' ')[0] 
                            
                            def fix_time(t):
                                t = t.replace('.', ',')
                                if t.count(':') == 1: 
                                    t = "00:" + t
                                return t
                            
                            current_start = fix_time(start)
                            current_end = fix_time(end)
                            
                        elif clean_line:
                             # Texto: remover tags complexas <00:00:00.560><c> etc
                             # O YouTube usa formato karaoke. Ex: "Quanto<...> custa<...>"
                             # Precisamos do texto limpo.
                             text = re.sub(r'<[^>]+>', '', clean_line).strip()
                             
                             if not text: continue
                             
                             # Lógica para remover duplicatas do estilo "Roll-up" ou "Karaoke"
                             # O YouTube repete a linha anterior às vezes.
                             # Ex:
                             # 1: "Quanto custa"
                             # 2: "Quanto custa\nQuantos quilos"
                             
                             # Vamos pegar apenas a ULTIMA linha se tiver quebras
                             lines_in_text = text.split('\n')
                             final_line = lines_in_text[-1].strip()
                             
                             if not final_line: continue

                             # Filtro de duplicidade consecutivo
                             if final_line == last_text:
                                 continue
                             
                             # Evita blocos ultra curtos (glitch de 10ms) que repetem texto
                             # Mas aqui estamos processando texto.
                             
                             srt_content.append(f"{counter}\n")
                             srt_content.append(f"{current_start} --> {current_end}\n")
                             srt_content.append(f"{final_line}\n\n")
                             
                             last_text = final_line
                             counter += 1
                    
                    with open(new_name, 'w', encoding='utf-8') as f_out:
                        f_out.writelines(srt_content)
                    
                    try:
                        print(i18n("Subtitle converted and cleaned: {}").format(new_name))
                    except UnicodeEncodeError:
                        print(i18n("Subtitle converted and cleaned: {}").format(new_name.encode('ascii', 'replace').decode('ascii')))
                    try: os.remove(best_sub) 
                    except: pass
                    
                except Exception as e_conv:
                    print(i18n("Failed to convert VTT: {}. Keeping original.").format(e_conv))
                    # Fallback: rename apenas
                    new_name_fallback = os.path.join(project_folder, "input.vtt")
                    if os.path.exists(new_name_fallback) and new_name_fallback != best_sub:
                        try: os.remove(new_name_fallback)
                        except: pass
                    os.rename(best_sub, new_name_fallback)

            else:
                # Já é SRT, só renomeia
                if os.path.exists(new_name) and new_name != best_sub:
                    try: os.remove(new_name)
                    except: pass
                os.rename(best_sub, new_name)
                try:
                    print(i18n("SRT subtitle renamed to: {}").format(new_name))
                except UnicodeEncodeError:
                    print(i18n("SRT subtitle renamed to: {}").format(new_name.encode('ascii', 'replace').decode('ascii')))
            
            # Limpa sobras
            for extra in potential_subs[1:]:
                try: os.remove(extra)
                except: pass

    except Exception as e_ren:
        print(i18n("Error processing subtitles: {}").format(e_ren))

    return final_video_path, project_folder