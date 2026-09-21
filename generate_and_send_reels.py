import os
import csv
import time
import json
import random
import requests
import html
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

try:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip, AudioFileClip
except ImportError:
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip, AudioFileClip

# ========================================================
# CONFIGURACIÓ I PARÀMETRES
# ========================================================
TEST_MODE = False
FORCE_TYPE = os.getenv("FORCE_TYPE", None)  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, 'public_videos')
VIDEOS_CSV_DIR = os.path.join(BASE_DIR, 'videos')

STATE_PATH = os.path.join(BASE_DIR, 'next_video_type.txt')
USED_AUDIO_PATH = os.path.join(BASE_DIR, 'used_ig_audio.txt')

CSV_PATHS = {
    'type1': os.path.join(VIDEOS_CSV_DIR, 'video_phrases.csv'),
    'type2': os.path.join(VIDEOS_CSV_DIR, 'video_questions.csv'),
    'type3': os.path.join(VIDEOS_CSV_DIR, 'video_tests.csv'),
    'type4': os.path.join(VIDEOS_CSV_DIR, 'video_povs.csv'),
    'type5': os.path.join(VIDEOS_CSV_DIR, 'video_checklists.csv'),
}

FONT_SERIF_REG_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Regular.ttf')
FONT_SERIF_ITALIC_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Italic.ttf')
FONT_SANS_PATH = os.path.join(BASE_DIR, 'Poppins-Medium.ttf')

FONT_SERIF_REG_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
FONT_SERIF_ITALIC_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"
FONT_SANS_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf"

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FREESOUND_API_KEY = os.getenv("FREESOUND_API_KEY")
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
ZERNIO_TIKTOK_ACCOUNT_ID = os.getenv("ZERNIO_TIKTOK_ACCOUNT_ID")
ZERNIO_INSTAGRAM_ACCOUNT_ID = os.getenv("ZERNIO_INSTAGRAM_ACCOUNT_ID")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 📏 Dimensions cinematogràfiques amb Safe Area (920x920)
CANVAS_W, CANVAS_H = 1080, 1920
SQUARE_SIZE = 920
SQUARE_LEFT_X = (CANVAS_W - SQUARE_SIZE) // 2  # X = 80 (80px de marge a cada banda)
SQUARE_TOP_Y = (CANVAS_H - SQUARE_SIZE) // 2   # Y = 500

# ========================================================
# UTILITATS I HOSTING A GIT
# ========================================================

def clean_directory(dir_path):
    if os.path.exists(dir_path):
        for f in os.listdir(dir_path):
            p = os.path.join(dir_path, f)
            if os.path.isfile(p) or os.path.islink(p):
                os.remove(p)
    else:
        os.makedirs(dir_path, exist_ok=True)

def download_file(url, save_path):
    if not os.path.exists(save_path):
        res = requests.get(url)
        with open(save_path, 'wb') as f:
            f.write(res.content)

def commit_repo_files(paths, message):
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo: return False
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", "-A"] + list(paths), check=True)
        commit_res = subprocess.run(["git", "commit", "-m", message], check=False)
        subprocess.run(["git", "pull", "--rebase"], check=False)
        subprocess.run(["git", "push"], check=False)
        return commit_res.returncode == 0
    except Exception as e:
        print(f"⚠️ Error Git commit/push: {e}")
        return False

def get_public_video_url(file_path, run_tag):
    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if not repo: raise Exception("❌ Falta la variable GITHUB_REPOSITORY.")

    fname = os.path.basename(file_path)
    print(f"📤 Pujant vídeo al repositori de GitHub (Tag: {run_tag})...")
    commit_repo_files(["public_videos/"], f"upload: video v{run_tag}")

    return f"https://raw.githubusercontent.com/{repo}/{branch}/public_videos/{fname}?v={run_tag}"

def send_telegram_text(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=payload, timeout=20)
        print("📲 Notificació de text enviada a Telegram!")
    except Exception as e:
        print(f"⚠️ Error enviant text a Telegram: {e}")

# ========================================================
# DESCÀRREGA DE MÚSICA FREESOUND (PER A TIKTOK)
# ========================================================

def download_freesound_romantic_music():
    if not FREESOUND_API_KEY:
        return None

    queries = [
        "romantic piano soft", "soft acoustic guitar romantic", 
        "romantic ambient background", "peaceful piano romance",
        "soft cinematic romantic piano", "peaceful chill lofi", "warm ambient piano"
    ]
    query = random.choice(queries)
    url = "https://freesound.org/apiv2/search/text/"
    params = {
        "query": query,
        "filter": "duration:[12 TO 120]",
        "fields": "id,name,previews,duration",
        "page_size": 15,
        "token": FREESOUND_API_KEY
    }

    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                selected = random.choice(results)
                previews = selected.get("previews", {})
                mp3_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
                if mp3_url:
                    audio_res = requests.get(mp3_url, timeout=20)
                    audio_path = os.path.join(BASE_DIR, "temp_freesound_bg.mp3")
                    with open(audio_path, "wb") as f:
                        f.write(audio_res.content)
                    print(f"✅ Música Freesound descarregada: '{selected.get('name')}'")
                    return audio_path
    except Exception as e:
        print(f"⚠️ Error Freesound: {e}")
    return None

# ========================================================
# GESTIÓ D'ÀUDIO EN TENDÈNCIA D'INSTAGRAM (SENSE REPETIR)
# ========================================================

def load_used_audio_ids():
    if os.path.exists(USED_AUDIO_PATH):
        with open(USED_AUDIO_PATH, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

def save_used_audio_id(audio_id):
    used = load_used_audio_ids()
    used.append(audio_id)
    used = used[-25:]
    with open(USED_AUDIO_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(used))

def get_instagram_trending_audio_id(account_id):
    used_ids = load_used_audio_ids()
    headers = {"Authorization": f"Bearer {ZERNIO_API_KEY}"}
    queries = ["", "love", "romantic", "piano", "acoustic", "sunset"]
    random.shuffle(queries)

    for q in queries:
        try:
            url = f"https://zernio.com/api/v1/accounts/{account_id}/instagram/audio"
            params = {"audioType": "music"}
            if q: params["q"] = q

            res = requests.get(url, headers=headers, params=params, timeout=15)
            if res.status_code == 200:
                tracks = res.json().get("audio", [])
                fresh_tracks = [t for t in tracks if t.get("audioId") and t.get("audioId") not in used_ids]
                candidate_tracks = fresh_tracks if fresh_tracks else tracks
                if candidate_tracks:
                    chosen = random.choice(candidate_tracks[:10])
                    audio_id = chosen.get("audioId")
                    save_used_audio_id(audio_id)
                    print(f"🎵 Àudio Instagram NOU: '{chosen.get('title')}' de {chosen.get('displayArtist')} (ID: {audio_id})")
                    return audio_id
        except Exception as e:
            print(f"⚠️ Error cercant música a Instagram: {e}")

    return None

# ========================================================
# PEXELS & CAPES GRÀFIQUES (AMB FILTRE FOSC I SAFE AREA)
# ========================================================

def download_pexels_videos(count):
    queries = [
        "scenic nature landscape vertical", "peaceful ocean sunset vertical", 
        "calm forest trees vertical", "mountain reflection lake vertical",
        "autumn nature landscape vertical", "golden hour ocean waves vertical"
    ]
    random.shuffle(queries)
    if not PEXELS_API_KEY: raise Exception("Falta PEXELS_API_KEY.")

    headers = {"Authorization": PEXELS_API_KEY}
    downloaded = []
    for i in range(count):
        q = queries[i % len(queries)]
        url = f"https://api.pexels.com/videos/search?query={q}&orientation=portrait&per_page=15&min_width=1080&min_height=1080"
        res = requests.get(url, headers=headers, timeout=15).json()
        videos = res.get("videos", [])
        if videos:
            v_files = random.choice(videos).get("video_files", [])
            hd = [f for f in v_files if f.get("file_type") == "video/mp4" and (f.get("height", 0) >= 1080 or f.get("width", 0) >= 1080)]
            best = max(hd, key=lambda f: f.get("width", 0) * f.get("height", 0)) if hd else v_files[0]
            v_res = requests.get(best["link"], timeout=30)
            p = os.path.join(BASE_DIR, f"temp_pexels_{i}.mp4")
            with open(p, "wb") as f:
                f.write(v_res.content)
            downloaded.append(p)
    return downloaded

def wrap_text(text, draw, font, max_width):
    lines, words = [], str(text).split(' ')
    if not words: return lines
    cur = words[0]
    for w in words[1:]:
        test_line = cur + ' ' + w
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width: cur = test_line
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines

def draw_text_centered_with_shadow(draw, text, font, y_pos, fill_color='#FFFFFF', shadow_color='#000000'):
    """Dibuixa text centrat amb ombra reforçada per garantir 100% de llegibilitat."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (CANVAS_W - tw) / 2
    # Ombra multidireccional per a un contrast perfecte
    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (2, 2), (-2, -2)]:
        draw.text((x + ox, y_pos + oy), text, fill=shadow_color, font=font)
    draw.text((x, y_pos), text, fill=fill_color, font=font)
    return (bbox[3] - bbox[1])

def draw_text_left_with_shadow(draw, text, font, x_pos, y_pos, fill_color='#FFFFFF', shadow_color='#000000'):
    """Dibuixa text alineat a l'esquerra amb ombra reforçada."""
    bbox = draw.textbbox((0, 0), text, font=font)
    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (2, 2), (-2, -2)]:
        draw.text((x_pos + ox, y_pos + oy), text, fill=shadow_color, font=font)
    draw.text((x_pos, y_pos), text, fill=fill_color, font=font)
    return (bbox[3] - bbox[1])

def create_base_square_overlay():
    """
    Crea la capa RGBA 1080x1920:
    - 100% Negre opac fora del quadrat de 920x920.
    - Dins del quadrat arrodonit: filtre fosc semitransparent (~50% d'opacitat)
      perquè qualsevol vídeo tingui un contrast excel·lent amb el text blanc.
    """
    frame = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 255))
    blur_r = 10
    radius = 50

    sq_left = SQUARE_LEFT_X
    sq_top = SQUARE_TOP_Y
    sq_right = SQUARE_LEFT_X + SQUARE_SIZE
    sq_bottom = SQUARE_TOP_Y + SQUARE_SIZE

    mask = Image.new('L', (CANVAS_W, CANVAS_H), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([(sq_left, sq_top), (sq_right, sq_bottom)], radius=radius, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_r))

    # Dins del quadrat (on la màscara és 255): apliquem opacitat de 130 (~51% de negre fosc)
    alpha_channel = Image.eval(mask, lambda val: int(255 - (val / 255.0) * (255 - 130)))
    frame.putalpha(alpha_channel)
    return frame

def add_footer_to_overlay(draw_obj, font_sans):
    draw_text_centered_with_shadow(draw_obj, "coupleforms", font_sans, SQUARE_TOP_Y + SQUARE_SIZE - 75, fill_color=(255, 255, 255, 230))

def generate_overlay_type1(data, font_serif, font_sans):
    base = create_base_square_overlay()
    draw = ImageDraw.Draw(base)
    lines = wrap_text(data.get('Phrase', ''), draw, font_serif, max_width=740)
    line_h = [draw.textbbox((0, 0), l, font=font_serif)[3] - draw.textbbox((0, 0), l, font=font_serif)[1] for l in lines]
    y_curr = SQUARE_TOP_Y + (SQUARE_SIZE - (sum(line_h) + (24 * (len(lines) - 1)))) / 2
    for l in lines:
        h = draw_text_centered_with_shadow(draw, l, font_serif, y_curr)
        y_curr += h + 24
    add_footer_to_overlay(draw, font_sans)
    p = os.path.join(BASE_DIR, "temp_frame_t1.png")
    base.save(p)
    return p

def generate_overlays_type2(data, font_title, font_q, font_sans):
    frames = []
    texts = [data.get('Title', ''), data.get('Question_1', ''), data.get('Question_2', ''), data.get('Question_3', '')]
    for idx, text in enumerate(texts):
        base = create_base_square_overlay()
        draw = ImageDraw.Draw(base)
        font = font_title if idx == 0 else font_q
        lines = wrap_text(text, draw, font, max_width=740)
        line_h = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]
        y_curr = SQUARE_TOP_Y + (SQUARE_SIZE - (sum(line_h) + (20 * (len(lines) - 1)))) / 2
        if idx > 0:
            draw_text_centered_with_shadow(draw, f"QUESTION 0{idx}", font_sans, y_curr - 80, fill_color='#E0E0E0')
        for l in lines:
            h = draw_text_centered_with_shadow(draw, l, font, y_curr)
            y_curr += h + 20
        add_footer_to_overlay(draw, font_sans)
        p = os.path.join(BASE_DIR, f"temp_frame_t2_{idx}.png")
        base.save(p)
        frames.append(p)
    return frames

def generate_overlay_type3(data, font_title, font_q, font_opt, font_sans):
    base = create_base_square_overlay()
    draw = ImageDraw.Draw(base)
    q_lines = wrap_text(data.get('Question', ''), draw, font_q, max_width=740)
    line_h = [draw.textbbox((0, 0), l, font=font_q)[3] - draw.textbbox((0, 0), l, font=font_q)[1] for l in q_lines]
    y_curr = SQUARE_TOP_Y + (SQUARE_SIZE - (sum(line_h) + 150)) / 2
    for l in q_lines:
        h = draw_text_centered_with_shadow(draw, l, font_q, y_curr)
        y_curr += h + 16
    y_curr += 40
    for opt in ("A) You", "B) Me"):
        h = draw_text_centered_with_shadow(draw, opt, font_opt, y_curr)
        y_curr += h + 24
    add_footer_to_overlay(draw, font_sans)
    p = os.path.join(BASE_DIR, "temp_frame_t3.png")
    base.save(p)
    return p

def generate_overlay_type4(data, font_serif, font_sans):
    return generate_overlay_type1(data, font_serif, font_sans)

def generate_overlays_type5(data, font_title, font_item, font_sans):
    """Genera les diapositives de la llista calculant els salts de línia automàtics."""
    title = data.get('Title', '')
    raw_items = [data.get('Item_1', ''), data.get('Item_2', ''), data.get('Item_3', ''), data.get('Item_4', '')]
    frames = []

    for count in range(1, 5):
        base = create_base_square_overlay()
        draw = ImageDraw.Draw(base)
        y_curr = SQUARE_TOP_Y + 130

        # Títol amb salt de línia
        t_lines = wrap_text(title, draw, font_title, max_width=720)
        for tl in t_lines:
            h = draw_text_centered_with_shadow(draw, tl, font_title, y_curr)
            y_curr += h + 8

        y_curr += 35

        # Punts de la llista amb càlcul de salt de línia
        for idx in range(count):
            item_raw = raw_items[idx].strip()
            # Si la frase és llarga, es divideix en múltiples línies (màx. 680px)
            wrapped_lines = wrap_text(f"•  {item_raw}", draw, font_item, max_width=680)
            
            for line_idx, line in enumerate(wrapped_lines):
                x_pos = SQUARE_LEFT_X + 110 if line_idx == 0 else SQUARE_LEFT_X + 140
                h = draw_text_left_with_shadow(draw, line, font_item, x_pos, y_curr)
                y_curr += h + 6
            y_curr += 16  # Espai entre ítems

        add_footer_to_overlay(draw, font_sans)
        p = os.path.join(BASE_DIR, f"temp_frame_t5_{count}.png")
        base.save(p)
        frames.append(p)
    return frames

# ========================================================
# RENDERITZACIÓ DE VÍDEO (REDUÏT A 920x920 I CENTRAT)
# ========================================================

def render_moviepy_reel_with_audio(bg_video_paths, overlay_paths, duration_per_frame, output_path, bg_audio_path=None):
    print("⚙️ Ensamblant vídeo (920x920 amb Safe Area) i pista d'àudio...")
    total_duration = sum(duration_per_frame)
    num_videos = len(bg_video_paths)
    segment_duration = total_duration / num_videos

    bg_black = ColorClip(size=(CANVAS_W, CANVAS_H), color=(0, 0, 0), duration=total_duration)
    raw_bg_clips, subclips, overlay_clips = [], [], []
    audio_clip = None
    final_clip = None

    try:
        start_t = 0
        for path in bg_video_paths:
            c = VideoFileClip(path)
            raw_bg_clips.append(c)
            dur = min(segment_duration, c.duration)
            c_sub = c.subclipped(0, dur) if hasattr(c, 'subclipped') else c.subclip(0, dur)
            
            # Retall quadrat 920x920
            c_sq = (c_sub.cropped(x_center=c_sub.w/2, y_center=c_sub.h/2, width=SQUARE_SIZE, height=SQUARE_SIZE)
                    if hasattr(c_sub, 'cropped') else
                    c_sub.crop(x_center=c_sub.w/2, y_center=c_sub.h/2, width=SQUARE_SIZE, height=SQUARE_SIZE))
            
            c_sq = c_sq.resized((SQUARE_SIZE, SQUARE_SIZE)) if hasattr(c_sq, 'resized') else c_sq.resize((SQUARE_SIZE, SQUARE_SIZE))
            
            # Posicionat exactament centrat a X=80, Y=500
            c_sq = (c_sq.with_position((SQUARE_LEFT_X, SQUARE_TOP_Y)).with_start(start_t)
                    if hasattr(c_sq, 'with_position') else
                    c_sq.set_position((SQUARE_LEFT_X, SQUARE_TOP_Y)).set_start(start_t))
            try:
                if hasattr(c_sq, 'fadein') and hasattr(c_sq, 'fadeout'):
                    c_sq = c_sq.fadein(0.3).fadeout(0.3)
            except Exception: pass
            subclips.append(c_sq)
            start_t += dur

        start_time = 0
        for idx, img_p in enumerate(overlay_paths):
            dur = duration_per_frame[idx]
            img_clip = ImageClip(img_p)
            img_clip = img_clip.with_start(start_time) if hasattr(img_clip, 'with_start') else img_clip.set_start(start_time)
            img_clip = img_clip.with_duration(dur) if hasattr(img_clip, 'with_duration') else img_clip.set_duration(dur)
            overlay_clips.append(img_clip)
            start_time += dur

        final_clip = CompositeVideoClip([bg_black] + subclips + overlay_clips)

        # 🎵 Integració de la música de Freesound al fitxer MP4
        if bg_audio_path and os.path.exists(bg_audio_path):
            try:
                audio_clip = AudioFileClip(bg_audio_path)
                if audio_clip.duration < total_duration:
                    try:
                        from moviepy.audio.fx.audio_loop import audio_loop
                        audio_clip = audio_loop(audio_clip, duration=total_duration)
                    except Exception: pass
                else:
                    audio_clip = audio_clip.subclipped(0, total_duration) if hasattr(audio_clip, 'subclipped') else audio_clip.subclip(0, total_duration)

                if hasattr(audio_clip, 'volumex'):
                    audio_clip = audio_clip.volumex(0.30)

                try:
                    if hasattr(audio_clip, 'audio_fadeout'):
                        audio_clip = audio_clip.audio_fadeout(0.8)
                except Exception: pass

                if hasattr(final_clip, 'set_audio'):
                    final_clip = final_clip.set_audio(audio_clip)
                elif hasattr(final_clip, 'with_audio'):
                    final_clip = final_clip.with_audio(audio_clip)
            except Exception as e_aud:
                print(f"⚠️ Error processant l'àudio de Freesound: {e_aud}")

        has_audio = audio_clip is not None
        final_clip.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio=has_audio,
            audio_codec="aac" if has_audio else None,
            preset="fast", 
            threads=2
        )
        print("✅ Reel renderitzat amb èxit!")
    finally:
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
# PUBLICACIÓ VIA ZERNIO
# ========================================================

def post_reel_to_zernio(video_url, title):
    zernio_url = "https://zernio.com/api/v1/posts"
    headers = {"Authorization": f"Bearer {ZERNIO_API_KEY}", "Content-Type": "application/json"}

    clean_title = title.strip()

    tiktok_content = (
        f"{clean_title}\n\n"
        "Send this to your person ❤️\n"
        "Play online for free at formfriends.com (no sign-up needed)\n\n"
        "—\n#couples #relationshipgoals #couplesreels #formfriends"
    )

    instagram_content = (
        f"{clean_title}\n\n"
        "Tag your person in the comments ❤️\n\n"
        "Comment 'LOVE' and we'll DM you the link to play!\n"
        "(Online, 100% free, no sign-up needed)\n\n"
        "—\n#couples #relationshipgoals #couplesreels #formfriends"
    )

    # 1. TikTok: So Original integrat a l'arxiu (sense CML ni bloquejos)
    tiktok_settings = {
        "privacy_level": "PUBLIC_TO_EVERYONE",
        "allow_comment": True,
        "allow_duet": True,
        "allow_stitch": True,
        "video_cover_timestamp_ms": 1500,
        "content_preview_confirmed": True,
        "express_consent_given": True
    }

    # 2. Instagram: Silenciem el vídeo (videoVolume: 0) i posem la cançó en tendència (audioVolume: 100)
    instagram_platform_data = {
        "shareToFeed": False,
        "thumbOffset": 1500,
        "firstComment": "Follow us & comment LOVE and we'll send you the direct link! ✨ (Online, 100% free, no sign-up needed)"
    }
    
    ig_audio_id = get_instagram_trending_audio_id(ZERNIO_INSTAGRAM_ACCOUNT_ID)
    if ig_audio_id:
        instagram_platform_data["audioConfiguration"] = {
            "audioId": ig_audio_id,
            "audioVolume": 100,
            "videoVolume": 0
        }

    media_items = [{"type": "video", "url": video_url}]
    payload = {
        "content": clean_title[:90],
        "media_items": media_items,
        "mediaItems": media_items,
        "platforms": [
            {
                "platform": "tiktok",
                "accountId": ZERNIO_TIKTOK_ACCOUNT_ID,
                "content": tiktok_content,
                "tiktok_settings": tiktok_settings,
                "tiktokSettings": tiktok_settings
            },
            {
                "platform": "instagram",
                "accountId": ZERNIO_INSTAGRAM_ACCOUNT_ID,
                "content": instagram_content,
                "platformSpecificData": instagram_platform_data
            }
        ],
        "tiktok_settings": tiktok_settings,
        "tiktokSettings": tiktok_settings,
        "publish_now": True,
        "publishNow": True
    }

    print("📤 Enviant Reel a Zernio (TikTok + Instagram)...")
    res = requests.post(zernio_url, headers=headers, json=payload, timeout=120)

    print(f"\n==================== RESPOSTA API ZERNIO (HTTP {res.status_code}) ====================")
    try:
        data = res.json()
        print(json.dumps(data, indent=2))
        platforms = data.get("post", {}).get("platforms", [])
        for p in platforms:
            p_name = p.get("platform")
            p_status = p.get("status")
            p_err = p.get("errorMessage")
            if p_err: print(f"⚠️ ALERTA PLATAFORMA [{p_name}]: {p_err}")
            else: print(f"✅ Plataforma [{p_name}] -> Estat: {p_status}")
    except Exception:
        print(res.text)
    print("========================================================================\n")

    return res.status_code in (200, 201)

# ========================================================
# GESTIÓ CSV
# ========================================================

def read_csv_safe(csv_path):
    if not os.path.exists(csv_path): return None, None
    rows, headers = [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try: headers = [h.strip() for h in next(reader)]
        except StopIteration: return None, None
        for r in reader:
            if r and any(field.strip() for field in r): rows.append(r)
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
    pref = 'type1'
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            v = f.read().strip()
            if v in CSV_PATHS: pref = v

    types_order = [pref] + [t for t in CSV_PATHS.keys() if t != pref]
    for post_type in types_order:
        csv_path = CSV_PATHS[post_type]
        headers, rows = read_csv_safe(csv_path)
        if not headers or 'Status' not in headers: continue
        status_idx = headers.index('Status')
        for idx, r in enumerate(rows):
            if r[status_idx].strip().lower() == 'pending':
                return post_type, csv_path, headers, rows, idx, dict(zip(headers, r))
    return None, None, None, None, None, None

def cleanup_temp_files(paths):
    for p in paths:
        if p and os.path.exists(p):
            try: os.remove(p)
            except Exception: pass

# ========================================================
# MAIN
# ========================================================

def main():
    download_file(FONT_SERIF_REG_URL, FONT_SERIF_REG_PATH)
    download_file(FONT_SERIF_ITALIC_URL, FONT_SERIF_ITALIC_PATH)
    download_file(FONT_SANS_URL, FONT_SANS_PATH)
    
    clean_directory(VIDEOS_DIR)

    post_type, csv_path, headers, rows, current_idx, data = pick_reel_type_to_process()
    if not post_type:
        print("🎉 Tots els vídeos estan completats ('Done')!")
        return

    RUN_TAG = int(time.time())
    video_id = data.get('Video_ID', 'Reel_1')
    print(f"🚀 Generant Reel {video_id} ({post_type}) amb Tag: {RUN_TAG}...")

    font_serif = ImageFont.truetype(FONT_SERIF_REG_PATH, 50)
    font_serif_large = ImageFont.truetype(FONT_SERIF_REG_PATH, 54)
    font_serif_italic = ImageFont.truetype(FONT_SERIF_ITALIC_PATH, 42)
    font_sans = ImageFont.truetype(FONT_SANS_PATH, 26)

    overlay_paths, durations, bg_video_paths = [], [], []
    bg_audio_path = None
    
    try:
        if post_type == 'type1':
            overlay_paths, durations = [generate_overlay_type1(data, font_serif_large, font_sans)], [8.0]
            caption_title = data.get('Phrase', '')
        elif post_type == 'type2':
            overlay_paths = generate_overlays_type2(data, font_serif_large, font_serif, font_sans)
            durations = [3.2, 3.6, 3.6, 3.6]
            caption_title = data.get('Title', '')
        elif post_type == 'type3':
            overlay_paths = [generate_overlay_type3(data, font_serif_large, font_serif, font_serif_italic, font_sans)]
            durations = [9.0]
            caption_title = data.get('Question', '')
        elif post_type == 'type4':
            overlay_paths, durations = [generate_overlay_type4(data, font_serif, font_sans)], [10.0]
            caption_title = data.get('Phrase', '')
        elif post_type == 'type5':
            overlay_paths = generate_overlays_type5(data, font_serif_large, font_serif, font_sans)
            durations = [3.0, 3.0, 3.0, 3.0]
            caption_title = data.get('Title', '')

        num_bg_videos = max(2, int(round(sum(durations) / 4.0)))
        bg_video_paths = download_pexels_videos(num_bg_videos)
        
        bg_audio_path = download_freesound_romantic_music()

        video_output_path = os.path.join(VIDEOS_DIR, f"{video_id}_v{RUN_TAG}.mp4")
        render_moviepy_reel_with_audio(bg_video_paths, overlay_paths, durations, video_output_path, bg_audio_path=bg_audio_path)

        status_idx = headers.index('Status')
        rows[current_idx][status_idx] = 'Done'
        write_csv_safe(csv_path, headers, rows)

        next_type = save_next_video_type(post_type)
        csv_relpath = os.path.relpath(csv_path, BASE_DIR)
        state_relpath = os.path.relpath(STATE_PATH, BASE_DIR)
        audio_state_relpath = os.path.relpath(USED_AUDIO_PATH, BASE_DIR) if os.path.exists(USED_AUDIO_PATH) else None

        git_paths = [csv_relpath, state_relpath]
        if audio_state_relpath: git_paths.append(audio_state_relpath)

        public_url = get_public_video_url(video_output_path, RUN_TAG)

        if TEST_MODE:
            msg = (
                f"🧪 <b>[MODE PROVA - REEL]</b>\n\n"
                f"📌 <b>ID:</b> {video_id} ({post_type})\n"
                f"🏷️ <b>Tag Cache:</b> {RUN_TAG}\n"
                f"📖 <b>Títol:</b> {html.escape(caption_title)}\n\n"
                f"🔗 <b>Enllaç del Vídeo (GitHub):</b>\n{public_url}"
            )
            send_telegram_text(msg)
            commit_repo_files(git_paths, f"chore: {video_id} -> Done (mode prova)")
        else:
            if not ZERNIO_API_KEY: raise Exception("⚠️ Falta ZERNIO_API_KEY.")
            if post_reel_to_zernio(public_url, caption_title):
                msg = (
                    f"🚀 <b>Reel Publicat!</b>\n\n"
                    f"📌 <b>ID:</b> {video_id} ({post_type})\n"
                    f"🏷️ <b>Tag Cache:</b> {RUN_TAG}\n"
                    f"📖 <b>Títol:</b> {html.escape(caption_title)}\n\n"
                    f"🔗 <b>Fitxer Vídeo (GitHub):</b>\n{public_url}"
                )
                send_telegram_text(msg)
            commit_repo_files(git_paths, f"chore: {video_id} -> Done ({post_type})")

    finally:
        all_temp = overlay_paths + bg_video_paths
        if bg_audio_path: all_temp.append(bg_audio_path)
        cleanup_temp_files(all_temp)

if __name__ == "__main__":
    main()