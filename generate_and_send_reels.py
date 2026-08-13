import os
import csv
import random
import requests
import html
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

# 🛠️ Fix per a compatibilitat de MoviePy 1.0.3 amb Pillow >= 10.0.0
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# Imports compatibles tant amb MoviePy v1.x com v2.x
try:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip, AudioFileClip, concatenate_videoclips

# ========================================================
# CONFIGURACIÓ I PARÀMETRES DE PROVA
# ========================================================
# Es pot configurar per entorn (TEST_MODE="true") o canviar directament a False per a producció
TEST_MODE = False

# Permet forçar un tipus de vídeo específic ('type1', 'type2', 'type3', 'type4', 'type5' o None)
FORCE_TYPE = os.getenv("FORCE_TYPE", None)  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, 'public_videos')
VIDEOS_CSV_DIR = os.path.join(BASE_DIR, 'videos')

STATE_PATH = os.path.join(BASE_DIR, 'next_video_type.txt')

CSV_PATHS = {
    'type1': os.path.join(VIDEOS_CSV_DIR, 'video_phrases.csv'),     # Frase Central
    'type2': os.path.join(VIDEOS_CSV_DIR, 'video_questions.csv'),   # 3 Preguntes
    'type3': os.path.join(VIDEOS_CSV_DIR, 'video_tests.csv'),       # Test You / Me
    'type4': os.path.join(VIDEOS_CSV_DIR, 'video_povs.csv'),        # POV Poètic
    'type5': os.path.join(VIDEOS_CSV_DIR, 'video_checklists.csv'),  # Checklist
}

FONT_SERIF_REG_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Regular.ttf')
FONT_SERIF_ITALIC_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Italic.ttf')
FONT_SANS_PATH = os.path.join(BASE_DIR, 'Poppins-Medium.ttf')

FONT_SERIF_REG_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
FONT_SERIF_ITALIC_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"
FONT_SANS_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf"

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FREESOUND_API_KEY = os.getenv("FREESOUND_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")

CANVAS_W, CANVAS_H = 1080, 1920
SQUARE_SIZE = 1080
SQUARE_TOP_Y = (CANVAS_H - SQUARE_SIZE) // 2  # Y = 420 (Centrat verticalment)

# ========================================================
# UTILITATS GENERALS I DESCARREGUES
# ========================================================

def download_file(url, save_path):
    if not os.path.exists(save_path):
        print(f"📥 Descarregant font: {os.path.basename(save_path)}...")
        res = requests.get(url)
        with open(save_path, 'wb') as f:
            f.write(res.content)

def download_pexels_videos(count):
    """Descarrega 'count' vídeos verticals de NATURALESA pura HD de Pexels API"""
    queries = [
        "scenic nature landscape vertical", "peaceful ocean sunset vertical", 
        "calm forest trees vertical", "mountain reflection lake vertical",
        "autumn nature landscape vertical", "golden hour ocean waves vertical",
        "misty green forest vertical", "serene valley sunset vertical"
    ]
    random.shuffle(queries)
    
    if not PEXELS_API_KEY:
        print("⚠️ PEXELS_API_KEY no configurada en les variables d'entorn.")
        raise Exception("Falta PEXELS_API_KEY.")

    headers = {"Authorization": PEXELS_API_KEY}
    downloaded_paths = []
    
    print(f"🎬 Cercant {count} vídeos de naturalesa HD a Pexels API...")
    
    for i in range(count):
        query = queries[i % len(queries)]
        url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=15&min_width=1080&min_height=1080"
        res = requests.get(url, headers=headers, timeout=15).json()
        videos = res.get("videos", [])
        
        if videos:
            selected_video = random.choice(videos)
            video_files = selected_video.get("video_files", [])
            
            # Filtrem fitxers MP4 en alta definició (HD / >=1080p)
            hd_files = [f for f in video_files if f.get("file_type") == "video/mp4" and (f.get("height", 0) >= 1080 or f.get("width", 0) >= 1080)]
            best_file = max(hd_files, key=lambda f: f.get("width", 0) * f.get("height", 0)) if hd_files else video_files[0]
            
            v_res = requests.get(best_file["link"], timeout=30)
            p = os.path.join(BASE_DIR, f"temp_pexels_bg_{i}.mp4")
            with open(p, "wb") as f:
                f.write(v_res.content)
            downloaded_paths.append(p)
            
    if not downloaded_paths:
        raise Exception("No s'han pogut descarregar vídeos de Pexels.")
        
    print(f"✅ S'han descarregat {len(downloaded_paths)} vídeos de naturalesa!")
    return downloaded_paths

def download_freesound_romantic_music():
    """Cerca i descarrega una pista de música romàntica d'alta qualitat des de Freesound.org API v2"""
    if not FREESOUND_API_KEY:
        print("ℹ️ FREESOUND_API_KEY no configurada. El vídeo es generarà sense àudio de fons.")
        return None

    queries = [
        "romantic piano soft", "soft acoustic guitar romantic", 
        "romantic ambient background", "peaceful piano romance",
        "soft cinematic romantic piano"
    ]
    query = random.choice(queries)
    print(f"🎵 Cercant música romàntica a Freesound API ('{query}')...")

    url = "https://freesound.org/apiv2/search/text/"
    params = {
        "query": query,
        "filter": "duration:[10 TO 120]",
        "fields": "id,name,previews,duration",
        "page_size": 15,
        "token": FREESOUND_API_KEY
    }

    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            print(f"⚠️ Error Freesound API ({res.status_code}): {res.text[:100]}")
            return None

        data = res.json()
        results = data.get("results", [])
        if not results:
            print("⚠️ No s'han trobat resultats de música a Freesound.")
            return None

        selected = random.choice(results)
        previews = selected.get("previews", {})
        mp3_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")

        if not mp3_url:
            print("⚠️ No s'ha trobat enllaç MP3 per al so seleccionat.")
            return None

        print(f"📥 Descarregant àudio: '{selected.get('name')}'...")
        audio_res = requests.get(mp3_url, timeout=20)
        audio_path = os.path.join(BASE_DIR, "temp_freesound_bg.mp3")
        with open(audio_path, "wb") as f:
            f.write(audio_res.content)

        print("✅ Música de fons descarregada amb èxit des de Freesound!")
        return audio_path

    except Exception as e:
        print(f"⚠️ Error descarregant àudio de Freesound: {e}")
        return None

def wrap_text(text, draw, font, max_width):
    lines = []
    words = str(text).split(' ')
    if not words:
        return lines
    current_line = words[0]
    for word in words[1:]:
        test_line = current_line + ' ' + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines

def draw_text_centered_with_shadow(draw, text, font, y_pos, fill_color='#FFFFFF', shadow_color='#000000'):
    """Dibuixa text centrat horitzontalment amb una ombra fosca per llegibilitat"""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (CANVAS_W - tw) / 2
    
    draw.text((x + 2, y_pos + 2), text, fill=shadow_color, font=font)
    draw.text((x, y_pos), text, fill=fill_color, font=font)
    return (bbox[3] - bbox[1])

def commit_repo_files(paths, message):
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        print("ℹ️ No s'ha detectat GITHUB_REPOSITORY: s'omet el commit (execució local).")
        return False
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add"] + list(paths), check=True)
        commit_res = subprocess.run(["git", "commit", "-m", message], check=False)
        subprocess.run(["git", "pull", "--rebase"], check=False)
        subprocess.run(["git", "push"], check=False)
        return commit_res.returncode == 0
    except Exception as e:
        print(f"⚠️ Error fent commit/push: {e}")
        return False

# ==========================================================
# RENDERITZACIÓ DEL MARC QUADRAT RETRO SOBRE CANVAS VERTICAL
# ==========================================================

def create_base_square_overlay():
    """Crea la capa RGBA 1080x1920 que és 100% NEGRA OPACA a les barres superiors/inferiors
    i dibuixa el marc arrodonit sobre el quadrat centrat (Y=420)."""
    
    frame = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 255))
    
    blur_r = 10
    margin = 28
    radius = 60
    inner_m = margin - blur_r
    
    mask = Image.new('L', (CANVAS_W, CANVAS_H), 0)
    draw_mask = ImageDraw.Draw(mask)
    
    sq_top = SQUARE_TOP_Y + inner_m
    sq_bottom = SQUARE_TOP_Y + SQUARE_SIZE - inner_m
    sq_left = inner_m
    sq_right = CANVAS_W - inner_m
    
    draw_mask.rounded_rectangle(
        [(sq_left, sq_top), (sq_right, sq_bottom)],
        radius=radius + blur_r,
        fill=255
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_r))
    
    alpha_channel = Image.eval(mask, lambda val: int(255 - (val / 255.0) * (255 - 50)))
    frame.putalpha(alpha_channel)
    
    return frame

def add_footer_to_overlay(draw_obj, font_sans):
    """Afegeix la marca d'aigua inferior 'coupleforms' amb ombra"""
    text = "coupleforms"
    draw_text_centered_with_shadow(draw_obj, text, font_sans, SQUARE_TOP_Y + 920, fill_color=(255, 255, 255, 230))

# ========================================================
# GENERADORS DE CAPES GRAFIQUES PER A CADA TIPUS DE REEL
# ========================================================

def generate_overlay_type1(data, font_serif, font_sans):
    base = create_base_square_overlay()
    draw = ImageDraw.Draw(base)
    
    phrase = data.get('Phrase', '')
    lines = wrap_text(phrase, draw, font_serif, max_width=840)
    
    line_h = [draw.textbbox((0, 0), l, font=font_serif)[3] - draw.textbbox((0, 0), l, font=font_serif)[1] for l in lines]
    total_h = sum(line_h) + (24 * (len(lines) - 1))
    
    y_curr = SQUARE_TOP_Y + (SQUARE_SIZE - total_h) / 2
    for l in lines:
        h = draw_text_centered_with_shadow(draw, l, font_serif, y_curr)
        y_curr += h + 24
        
    add_footer_to_overlay(draw, font_sans)
    img_path = os.path.join(BASE_DIR, "temp_frame_t1.png")
    base.save(img_path)
    return img_path

def generate_overlays_type2(data, font_title, font_q, font_sans):
    frames = []
    texts = [
        data.get('Title', ''),
        data.get('Question_1', ''),
        data.get('Question_2', ''),
        data.get('Question_3', '')
    ]
    
    for idx, text in enumerate(texts):
        base = create_base_square_overlay()
        draw = ImageDraw.Draw(base)
        
        font = font_title if idx == 0 else font_q
        lines = wrap_text(text, draw, font, max_width=840)
        line_h = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]
        total_h = sum(line_h) + (20 * (len(lines) - 1))
        
        y_curr = SQUARE_TOP_Y + (SQUARE_SIZE - total_h) / 2
        
        if idx > 0:
            tag = f"QUESTION 0{idx}"
            draw_text_centered_with_shadow(draw, tag, font_sans, y_curr - 80, fill_color='#E0E0E0')

        for l in lines:
            h = draw_text_centered_with_shadow(draw, l, font, y_curr)
            y_curr += h + 20

        add_footer_to_overlay(draw, font_sans)
        f_path = os.path.join(BASE_DIR, f"temp_frame_t2_{idx}.png")
        base.save(f_path)
        frames.append(f_path)
        
    return frames

def generate_overlay_type3(data, font_title, font_q, font_opt, font_sans):
    base = create_base_square_overlay()
    draw = ImageDraw.Draw(base)
    
    question = data.get('Question', '')
    opt_a = "A) You"
    opt_b = "B) Me"
    
    q_lines = wrap_text(question, draw, font_q, max_width=840)
    line_h = [draw.textbbox((0, 0), l, font=font_q)[3] - draw.textbbox((0, 0), l, font=font_q)[1] for l in q_lines]
    total_q_h = sum(line_h) + (16 * (len(q_lines) - 1))
    
    total_content_h = total_q_h + 50 + 40 + 20 + 40
    y_curr = SQUARE_TOP_Y + (SQUARE_SIZE - total_content_h) / 2
    
    for l in q_lines:
        h = draw_text_centered_with_shadow(draw, l, font_q, y_curr)
        y_curr += h + 16
        
    y_curr += 40
    for opt in (opt_a, opt_b):
        h = draw_text_centered_with_shadow(draw, opt, font_opt, y_curr)
        y_curr += h + 24

    add_footer_to_overlay(draw, font_sans)
    f_path = os.path.join(BASE_DIR, "temp_frame_t3.png")
    base.save(f_path)
    return f_path

def generate_overlay_type4(data, font_serif, font_sans):
    base = create_base_square_overlay()
    draw = ImageDraw.Draw(base)
    
    phrase = data.get('Phrase', '')
    if not phrase:
        lines_text = [data.get('Line_1', ''), data.get('Line_2', ''), data.get('Line_3', '')]
        valid_lines = [l.strip() for l in lines_text if l.strip()]
        phrase = " ".join(valid_lines)
    
    lines = wrap_text(phrase, draw, font_serif, max_width=840)
    line_h = [draw.textbbox((0, 0), l, font=font_serif)[3] - draw.textbbox((0, 0), l, font=font_serif)[1] for l in lines]
    total_h = sum(line_h) + (24 * (len(lines) - 1))
    
    y_curr = SQUARE_TOP_Y + (SQUARE_SIZE - total_h) / 2
    for l in lines:
        h = draw_text_centered_with_shadow(draw, l, font_serif, y_curr)
        y_curr += h + 24
        
    add_footer_to_overlay(draw, font_sans)
    f_path = os.path.join(BASE_DIR, "temp_frame_t4.png")
    base.save(f_path)
    return f_path

def generate_overlays_type5(data, font_title, font_item, font_sans):
    title = data.get('Title', '')
    items = [data.get('Item_1', ''), data.get('Item_2', ''), data.get('Item_3', ''), data.get('Item_4', '')]
    frames = []
    
    for count in range(1, 5):
        base = create_base_square_overlay()
        draw = ImageDraw.Draw(base)
        
        y_curr = SQUARE_TOP_Y + 200
        
        t_lines = wrap_text(title, draw, font_title, max_width=840)
        for tl in t_lines:
            h = draw_text_centered_with_shadow(draw, tl, font_title, y_curr)
            y_curr += h + 10
            
        y_curr += 50
        
        for idx in range(count):
            item_text = f"-  {items[idx]}"
            draw.text((162, y_curr + 2), item_text, fill='#000000', font=font_item)
            draw.text((160, y_curr), item_text, fill='#FFFFFF', font=font_item)
            y_curr += 70

        add_footer_to_overlay(draw, font_sans)
        f_path = os.path.join(BASE_DIR, f"temp_frame_t5_{count}.png")
        base.save(f_path)
        frames.append(f_path)
        
    return frames

# =========================================================================
# ENSAMBLATGE DE VÍDEO AMB MOVIEPY (VÍDEO + ÀUDIO DE FREESOUND)
# =========================================================================

def render_moviepy_reel(bg_video_paths, overlay_paths, duration_per_frame, output_path, bg_audio_path=None):
    """Encaixa el vídeo de fons exactament a un quadrat de 1080x1080 a Y=420,
    aplica transició de fosa a negre, afegeix la capa de text i l'àudio de Freesound."""
    print(f"⚙️ Ensamblant vídeo final ({output_path}) amb MoviePy...")
    
    total_duration = sum(duration_per_frame)
    num_videos = len(bg_video_paths)
    segment_duration = total_duration / num_videos
    
    bg_black = ColorClip(size=(CANVAS_W, CANVAS_H), color=(0, 0, 0), duration=total_duration)
    
    raw_bg_clips = []
    subclips = []
    overlay_clips = []
    audio_clip = None
    final_clip = None
    
    try:
        start_t = 0
        for i, path in enumerate(bg_video_paths):
            c = VideoFileClip(path)
            raw_bg_clips.append(c)
            dur = min(segment_duration, c.duration)
            
            if hasattr(c, 'subclipped'):
                c_sub = c.subclipped(0, dur)
            else:
                c_sub = c.subclip(0, dur)
                
            if hasattr(c_sub, 'cropped'):
                c_sq = c_sub.cropped(x_center=c_sub.w / 2, y_center=c_sub.h / 2, width=SQUARE_SIZE, height=SQUARE_SIZE)
            else:
                c_sq = c_sub.crop(x_center=c_sub.w / 2, y_center=c_sub.h / 2, width=SQUARE_SIZE, height=SQUARE_SIZE)
                
            if hasattr(c_sq, 'resized'):
                c_sq = c_sq.resized((SQUARE_SIZE, SQUARE_SIZE))
            else:
                c_sq = c_sq.resize((SQUARE_SIZE, SQUARE_SIZE))
                
            if hasattr(c_sq, 'with_position'):
                c_sq = c_sq.with_position((0, SQUARE_TOP_Y)).with_start(start_t)
            else:
                c_sq = c_sq.set_position((0, SQUARE_TOP_Y)).set_start(start_t)
                
            try:
                if hasattr(c_sq, 'fadein') and hasattr(c_sq, 'fadeout'):
                    c_sq = c_sq.fadein(0.3).fadeout(0.3)
            except Exception:
                pass

            subclips.append(c_sq)
            start_t += dur

        start_time = 0
        for idx, img_p in enumerate(overlay_paths):
            dur = duration_per_frame[idx]
            img_clip = ImageClip(img_p)
            
            if hasattr(img_clip, 'with_start'):
                img_clip = img_clip.with_start(start_time)
            else:
                img_clip = img_clip.set_start(start_time)
                
            if hasattr(img_clip, 'with_duration'):
                img_clip = img_clip.with_duration(dur)
            else:
                img_clip = img_clip.set_duration(dur)
                
            overlay_clips.append(img_clip)
            start_time += dur
            
        final_clip = CompositeVideoClip([bg_black] + subclips + overlay_clips)

        # 🎵 Integració d'àudio romàntic si s'ha descarregat
        if bg_audio_path and os.path.exists(bg_audio_path):
            try:
                print("🎵 Processant i integrant l'àudio de fons des de Freesound...")
                audio_clip = AudioFileClip(bg_audio_path)

                # Si l'àudio és més curt que la durada del vídeo, el fem en bucle
                if audio_clip.duration < total_duration:
                    try:
                        from moviepy.audio.fx.audio_loop import audio_loop
                        audio_clip = audio_loop(audio_clip, duration=total_duration)
                    except Exception:
                        pass
                else:
                    if hasattr(audio_clip, 'subclipped'):
                        audio_clip = audio_clip.subclipped(0, total_duration)
                    else:
                        audio_clip = audio_clip.subclip(0, total_duration)

                # Reduïm el volum al 25% per ser música suau de fons
                if hasattr(audio_clip, 'volumex'):
                    audio_clip = audio_clip.volumex(0.25)

                # Fadeout d'àudio al final de 0.8 segons
                try:
                    if hasattr(audio_clip, 'audio_fadeout'):
                        audio_clip = audio_clip.audio_fadeout(0.8)
                    elif hasattr(audio_clip, 'fadeout'):
                        audio_clip = audio_clip.fadeout(0.8)
                except Exception:
                    pass

                # Afegim l'àudio al clip final
                if hasattr(final_clip, 'set_audio'):
                    final_clip = final_clip.set_audio(audio_clip)
                elif hasattr(final_clip, 'with_audio'):
                    final_clip = final_clip.with_audio(audio_clip)

            except Exception as e_audio:
                print(f"⚠️ Error processant l'àudio (es generarà el vídeo sense àudio): {e_audio}")

        has_audio = audio_clip is not None
        final_clip.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio=has_audio,
            audio_codec="aac" if has_audio else None, 
            preset="fast"
        )
        print("✅ Reel generat amb èxit!")

    finally:
        # 🧹 Tancament explícit per alliberar memòria RAM en CI/CD (GitHub Actions)
        if audio_clip:
            try: audio_clip.close()
            except: pass
        if final_clip:
            try: final_clip.close()
            except: pass
        for clip in subclips + overlay_clips + raw_bg_clips:
            try: clip.close()
            except: pass
        try: bg_black.close()
        except: pass

# ========================================================
# TELEGRAM / CSV / ROTACIÓ DE TIPUS
# ========================================================

def send_telegram_video(video_path, caption):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram no configurat.")
        return
    try:
        print("📲 Enviant vídeo a Telegram per a la revisió...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(video_path, 'rb') as f:
            files = {'video': f}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
            requests.post(url, data=data, files=files)
        print("✅ Vídeo enviat a Telegram!")
    except Exception as e:
        print(f"⚠️ Error enviant vídeo a Telegram: {e}")

def read_csv_safe(csv_path):
    if not os.path.exists(csv_path):
        return None, None
    rows, headers = [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            return None, None
        for r in reader:
            if r and any(field.strip() for field in r):
                rows.append(r)
    return headers, rows

def write_csv_safe(csv_path, headers, rows):
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def save_next_video_type(current_type):
    types = ['type1', 'type2', 'type3', 'type4', 'type5']
    next_type = types[(types.index(current_type) + 1) % len(types)] if current_type in types else 'type1'
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        f.write(next_type)
    return next_type

def pick_reel_type_to_process():
    if TEST_MODE and FORCE_TYPE and FORCE_TYPE in CSV_PATHS:
        print(f"🧪 [MODE SELECCIÓ MANUAL] Tipus forçat: {FORCE_TYPE}")
        preferred_type = FORCE_TYPE
    else:
        preferred_type = 'type1'
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                v = f.read().strip()
                if v in CSV_PATHS:
                    preferred_type = v

    types_order = [preferred_type] + [t for t in CSV_PATHS.keys() if t != preferred_type]
    
    for post_type in types_order:
        csv_path = CSV_PATHS[post_type]
        headers, rows = read_csv_safe(csv_path)
        if not headers or 'Status' not in headers:
            continue

        status_idx = headers.index('Status')
        for idx, r in enumerate(rows):
            if r[status_idx].strip().lower() == 'pending':
                post_data = dict(zip(headers, r))
                return post_type, csv_path, headers, rows, idx, post_data

    return None, None, None, None, None, None

def cleanup_temp_files(paths):
    """Elimina fitxers temporals de vídeo, àudio i imatges generats durant l'execució"""
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                print(f"⚠️ No s'ha pogut eliminar el fitxer temporal {p}: {e}")

# ========================================================
# MAIN
# ========================================================

def main():
    download_file(FONT_SERIF_REG_URL, FONT_SERIF_REG_PATH)
    download_file(FONT_SERIF_ITALIC_URL, FONT_SERIF_ITALIC_PATH)
    download_file(FONT_SANS_URL, FONT_SANS_PATH)
    
    os.makedirs(VIDEOS_DIR, exist_ok=True)

    post_type, csv_path, headers, rows, current_idx, data = pick_reel_type_to_process()
    
    if not post_type:
        print("🎉 Tots els vídeos de tots els CSVs estan completats ('Done')!")
        return

    video_id = data.get('Video_ID', 'Reel_1')
    print(f"🚀 Generant Reel ({post_type}) per a {video_id} des de {os.path.basename(csv_path)}...")

    font_serif = ImageFont.truetype(FONT_SERIF_REG_PATH, 52)
    font_serif_large = ImageFont.truetype(FONT_SERIF_REG_PATH, 58)
    font_serif_italic = ImageFont.truetype(FONT_SERIF_ITALIC_PATH, 44)
    font_sans = ImageFont.truetype(FONT_SANS_PATH, 28)

    overlay_paths = []
    durations = []
    bg_video_paths = []
    bg_audio_path = None
    
    try:
        if post_type == 'type1':
            f_path = generate_overlay_type1(data, font_serif_large, font_sans)
            overlay_paths, durations = [f_path], [8.0]
            caption_title = data.get('Phrase', '')

        elif post_type == 'type2':
            overlay_paths = generate_overlays_type2(data, font_serif_large, font_serif, font_sans)
            durations = [3.2, 3.6, 3.6, 3.6]
            caption_title = data.get('Title', '')

        elif post_type == 'type3':
            f_path = generate_overlay_type3(data, font_serif_large, font_serif, font_serif_italic, font_sans)
            overlay_paths, durations = [f_path], [9.0]
            caption_title = data.get('Question', '')

        elif post_type == 'type4':
            f_path = generate_overlay_type4(data, font_serif, font_sans)
            overlay_paths, durations = [f_path], [10.0]
            caption_title = data.get('Phrase', f"{data.get('Line_1', '')} {data.get('Line_2', '')}")

        elif post_type == 'type5':
            overlay_paths = generate_overlays_type5(data, font_serif_large, font_serif, font_sans)
            durations = [3.0, 3.0, 3.0, 3.0]
            caption_title = data.get('Title', '')

        total_duration = sum(durations)
        num_bg_videos = max(2, int(round(total_duration / 4.0)))
        
        # 1. Descarregar vídeos de fons de Pexels
        bg_video_paths = download_pexels_videos(num_bg_videos)
        
        # 2. Descarregar música romàntica de fons des de Freesound
        bg_audio_path = download_freesound_romantic_music()

        output_video_path = os.path.join(VIDEOS_DIR, f"{video_id}.mp4")
        
        # 3. Ensamblar el vídeo final amb imatges, fons de vídeo i pista d'àudio
        render_moviepy_reel(bg_video_paths, overlay_paths, durations, output_video_path, bg_audio_path=bg_audio_path)

        tags = "#couples #relationshipgoals #couplesreels #formfriends"
        caption = f"✨ <b>{html.escape(caption_title)}</b>\n\nTag your person in the comments ❤️\n\nPlay at formfriends.com\n\n{tags}"

        status_idx = headers.index('Status')
        rows[current_idx][status_idx] = 'Done'
        write_csv_safe(csv_path, headers, rows)

        next_type = save_next_video_type(post_type)

        csv_relpath = os.path.relpath(csv_path, BASE_DIR)
        state_relpath = os.path.relpath(STATE_PATH, BASE_DIR)

        if TEST_MODE:
            print("🧪 MODE PROVA ACTIVAT: S'omet Zernio. Enviant el vídeo a Telegram...")
            telegram_caption = f"🧪 <b>[MODE PROVA - REEL] {video_id} ({post_type})</b>\n\n{caption}"
            send_telegram_video(output_video_path, telegram_caption)
            
            commit_repo_files([csv_relpath, state_relpath], f"chore: {video_id} -> Done (mode prova, {post_type})")
            print(f"📝 CSV actualitzat a Git! {video_id} -> Done. Proper tipus: {next_type}.")

        else:
            print("📤 MODE PRODUCCIÓ: Publicació a Zernio...")
            send_telegram_video(output_video_path, f"🚀 <b>[PUBLICAT] {video_id}</b>\n\n{caption}")
            commit_repo_files([csv_relpath, state_relpath], f"chore: {video_id} -> Done ({post_type})")

    finally:
        # 🧹 Netegem els fitxers temporals de vídeo, imatge i àudio
        all_temp = overlay_paths + bg_video_paths
        if bg_audio_path:
            all_temp.append(bg_audio_path)
        cleanup_temp_files(all_temp)

if __name__ == "__main__":
    main()
