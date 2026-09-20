import os
import csv
import time
import random
import requests
import html
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

try:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip
except ImportError:
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip

# ========================================================
# CONFIGURACIÓ I PARÀMETRES
# ========================================================
TEST_MODE = False
FORCE_TYPE = os.getenv("FORCE_TYPE", None)  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, 'public_videos')
VIDEOS_CSV_DIR = os.path.join(BASE_DIR, 'videos')

STATE_PATH = os.path.join(BASE_DIR, 'next_video_type.txt')

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
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
ZERNIO_TIKTOK_ACCOUNT_ID = os.getenv("ZERNIO_TIKTOK_ACCOUNT_ID")
ZERNIO_INSTAGRAM_ACCOUNT_ID = os.getenv("ZERNIO_INSTAGRAM_ACCOUNT_ID")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CANVAS_W, CANVAS_H = 1080, 1920
SQUARE_SIZE = 1080
SQUARE_TOP_Y = (CANVAS_H - SQUARE_SIZE) // 2

# ========================================================
# UTILITATS I HOSTING A GIT
# ========================================================

def clean_directory(dir_path):
    """Buda completament els vídeos anteriors per mantenir lleuger el repo."""
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
# PEXELS & OVERLAYS
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
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (CANVAS_W - tw) / 2
    draw.text((x + 2, y_pos + 2), text, fill=shadow_color, font=font)
    draw.text((x, y_pos), text, fill=fill_color, font=font)
    return (bbox[3] - bbox[1])

def create_base_square_overlay():
    frame = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 255))
    blur_r, margin, radius = 10, 28, 60
    inner_m = margin - blur_r
    mask = Image.new('L', (CANVAS_W, CANVAS_H), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([(inner_m, SQUARE_TOP_Y + inner_m), (CANVAS_W - inner_m, SQUARE_TOP_Y + SQUARE_SIZE - inner_m)], radius=radius + blur_r, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_r))
    frame.putalpha(Image.eval(mask, lambda val: int(255 - (val / 255.0) * (255 - 50))))
    return frame

def add_footer_to_overlay(draw_obj, font_sans):
    draw_text_centered_with_shadow(draw_obj, "coupleforms", font_sans, SQUARE_TOP_Y + 920, fill_color=(255, 255, 255, 230))

def generate_overlay_type1(data, font_serif, font_sans):
    base = create_base_square_overlay()
    draw = ImageDraw.Draw(base)
    lines = wrap_text(data.get('Phrase', ''), draw, font_serif, 840)
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
        lines = wrap_text(text, draw, font, 840)
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
    q_lines = wrap_text(data.get('Question', ''), draw, font_q, 840)
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
    title = data.get('Title', '')
    items = [data.get('Item_1', ''), data.get('Item_2', ''), data.get('Item_3', ''), data.get('Item_4', '')]
    frames = []
    for count in range(1, 5):
        base = create_base_square_overlay()
        draw = ImageDraw.Draw(base)
        y_curr = SQUARE_TOP_Y + 200
        for tl in wrap_text(title, draw, font_title, 840):
            h = draw_text_centered_with_shadow(draw, tl, font_title, y_curr)
            y_curr += h + 10
        y_curr += 50
        for idx in range(count):
            draw.text((162, y_curr + 2), f"-  {items[idx]}", fill='#000000', font=font_item)
            draw.text((160, y_curr), f"-  {items[idx]}", fill='#FFFFFF', font=font_item)
            y_curr += 70
        add_footer_to_overlay(draw, font_sans)
        p = os.path.join(BASE_DIR, f"temp_frame_t5_{count}.png")
        base.save(p)
        frames.append(p)
    return frames

def render_moviepy_reel_silent(bg_video_paths, overlay_paths, duration_per_frame, output_path):
    print("⚙️ Ensamblant vídeo mut amb MoviePy...")
    total_duration = sum(duration_per_frame)
    num_videos = len(bg_video_paths)
    segment_duration = total_duration / num_videos

    bg_black = ColorClip(size=(CANVAS_W, CANVAS_H), color=(0, 0, 0), duration=total_duration)
    raw_bg_clips, subclips, overlay_clips = [], [], []

    try:
        start_t = 0
        for path in bg_video_paths:
            c = VideoFileClip(path)
            raw_bg_clips.append(c)
            dur = min(segment_duration, c.duration)
            c_sub = c.subclipped(0, dur) if hasattr(c, 'subclipped') else c.subclip(0, dur)
            c_sq = (c_sub.cropped(x_center=c_sub.w/2, y_center=c_sub.h/2, width=SQUARE_SIZE, height=SQUARE_SIZE)
                    if hasattr(c_sub, 'cropped') else
                    c_sub.crop(x_center=c_sub.w/2, y_center=c_sub.h/2, width=SQUARE_SIZE, height=SQUARE_SIZE))
            c_sq = c_sq.resized((SQUARE_SIZE, SQUARE_SIZE)) if hasattr(c_sq, 'resized') else c_sq.resize((SQUARE_SIZE, SQUARE_SIZE))
            c_sq = (c_sq.with_position((0, SQUARE_TOP_Y)).with_start(start_t)
                    if hasattr(c_sq, 'with_position') else
                    c_sq.set_position((0, SQUARE_TOP_Y)).set_start(start_t))
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
        final_clip.write_videofile(output_path, fps=24, codec="libx264", audio=False, preset="fast", threads=2)
        print("✅ Reel mut renderitzat correctament!")
    finally:
        for clip in subclips + overlay_clips + raw_bg_clips:
            try: clip.close()
            except: pass
        try: bg_black.close()
        except: pass

# ========================================================
# MÚSICA EN TENDÈNCIA I PUBLICACIÓ VIA ZERNIO
# ========================================================

def get_instagram_trending_audio_id(account_id):
    """Cerca cançó en tendència al catàleg d'Instagram."""
    try:
        url = f"https://zernio.com/api/v1/accounts/{account_id}/instagram/audio"
        headers = {"Authorization": f"Bearer {ZERNIO_API_KEY}"}
        res = requests.get(url, headers=headers, params={"audioType": "music"}, timeout=15)
        if res.status_code == 200:
            tracks = res.json().get("audio", [])
            if tracks:
                chosen = random.choice(tracks[:8])
                print(f"🎵 Àudio Instagram: '{chosen.get('title')}' ({chosen.get('audioId')})")
                return chosen.get("audioId")
    except Exception as e:
        print(f"⚠️ Error música Instagram: {e}")
    return None

def get_tiktok_trending_music_id(account_id):
    """Cerca cançó en tendència a la Commercial Music Library (CML) de TikTok."""
    try:
        url = f"https://zernio.com/api/v1/accounts/{account_id}/tiktok/commercial-music"
        headers = {"Authorization": f"Bearer {ZERNIO_API_KEY}"}
        res = requests.get(url, headers=headers, params={"countryCode": "US"}, timeout=15)
        if res.status_code == 200:
            tracks = res.json().get("tracks", [])
            if tracks:
                chosen = random.choice(tracks[:8])
                track_id = chosen.get("id") or chosen.get("clip", {}).get("id")
                print(f"🎵 Àudio TikTok (CML): '{chosen.get('name')}' (ID: {track_id})")
                return track_id
    except Exception as e:
        print(f"⚠️ Error música TikTok: {e}")
    return None

def post_reel_to_zernio(video_url, title):
    zernio_url = "https://zernio.com/api/v1/posts"
    headers = {"Authorization": f"Bearer {ZERNIO_API_KEY}", "Content-Type": "application/json"}

    clean_title = title.strip()

    # Text TikTok (sense menció a la bio)
    tiktok_content = (
        f"{clean_title}\n\n"
        "Send this to your person ❤️\n"
        "Play online for free at formfriends.com (no sign-up needed)\n\n"
        "—\n#couples #relationshipgoals #couplesreels #formfriends"
    )

    # Text Instagram (amb crida a comentar LOVE)
    instagram_content = (
        f"{clean_title}\n\n"
        "Tag your person in the comments ❤️\n\n"
        "Comment 'LOVE' and we'll DM you the link to play!\n"
        "(Online, 100% free, no sign-up needed)\n\n"
        "—\n#couples #relationshipgoals #couplesreels #formfriends"
    )

    # 1. Configuració de TikTok amb CML i portada a 1.5s
    tiktok_settings = {
        "privacy_level": "PUBLIC_TO_EVERYONE",
        "allow_comment": True,
        "allow_duet": True,
        "allow_stitch": True,
        "video_cover_timestamp_ms": 1500,
        "content_preview_confirmed": True,
        "express_consent_given": True
    }
    tiktok_music_id = get_tiktok_trending_music_id(ZERNIO_TIKTOK_ACCOUNT_ID)
    if tiktok_music_id:
        tiktok_settings["musicSoundInfo"] = {
            "musicSoundId": tiktok_music_id,
            "musicSoundVolume": 85
        }
        tiktok_settings["videoOriginalSoundVolume"] = 0

    # 2. Configuració d'Instagram amb catàleg, portada a 1.5s, no feed i comentari fixat
    instagram_platform_data = {
        "shareToFeed": False,
        "thumbOffset": 1500,
        "firstComment": "Follow us & comment LOVE and we'll send you the direct link! ✨ (Online, 100% free, no sign-up needed)"
    }
    ig_audio_id = get_instagram_trending_audio_id(ZERNIO_INSTAGRAM_ACCOUNT_ID)
    if ig_audio_id:
        instagram_platform_data["audioConfiguration"] = {
            "audioId": ig_audio_id,
            "audioVolume": 85,
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

    print("📤 Enviant Reel a Zernio (TikTok + Instagram simultani)...")
    res = requests.post(zernio_url, headers=headers, json=payload, timeout=120)
    if res.status_code in (200, 201):
        print("✅ Reel publicat amb èxit a ambdues plataformes!")
        return True
    else:
        print(f"❌ Error en publicar el Reel ({res.status_code}): {res.text}")
        return False

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

    font_serif = ImageFont.truetype(FONT_SERIF_REG_PATH, 52)
    font_serif_large = ImageFont.truetype(FONT_SERIF_REG_PATH, 58)
    font_serif_italic = ImageFont.truetype(FONT_SERIF_ITALIC_PATH, 44)
    font_sans = ImageFont.truetype(FONT_SANS_PATH, 28)

    overlay_paths, durations, bg_video_paths = [], [], []
    
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
        
        silent_video_path = os.path.join(VIDEOS_DIR, f"{video_id}_v{RUN_TAG}.mp4")
        render_moviepy_reel_silent(bg_video_paths, overlay_paths, durations, silent_video_path)

        status_idx = headers.index('Status')
        rows[current_idx][status_idx] = 'Done'
        write_csv_safe(csv_path, headers, rows)

        next_type = save_next_video_type(post_type)
        csv_relpath = os.path.relpath(csv_path, BASE_DIR)
        state_relpath = os.path.relpath(STATE_PATH, BASE_DIR)

        public_url = get_public_video_url(silent_video_path, RUN_TAG)

        if TEST_MODE:
            msg = (
                f"🧪 <b>[MODE PROVA - REEL]</b>\n\n"
                f"📌 <b>ID:</b> {video_id} ({post_type})\n"
                f"🏷️ <b>Tag Cache:</b> {RUN_TAG}\n"
                f"📖 <b>Títol:</b> {html.escape(caption_title)}\n\n"
                f"🔗 <b>Enllaç del Vídeo (GitHub):</b>\n{public_url}"
            )
            send_telegram_text(msg)
            commit_repo_files([csv_relpath, state_relpath], f"chore: {video_id} -> Done (mode prova)")
        else:
            if not ZERNIO_API_KEY: raise Exception("⚠️ Falta ZERNIO_API_KEY.")
            if post_reel_to_zernio(public_url, caption_title):
                msg = (
                    f"🚀 <b>Reel Publicat! (TikTok + Instagram)</b>\n\n"
                    f"📌 <b>ID:</b> {video_id} ({post_type})\n"
                    f"🏷️ <b>Tag Cache:</b> {RUN_TAG}\n"
                    f"📖 <b>Títol:</b> {html.escape(caption_title)}\n\n"
                    f"🔗 <b>Enllaç del Fitxer (GitHub):</b>\n{public_url}"
                )
                send_telegram_text(msg)
            commit_repo_files([csv_relpath, state_relpath], f"chore: {video_id} -> Done ({post_type})")

    finally:
        cleanup_temp_files(overlay_paths + bg_video_paths)

if __name__ == "__main__":
    main()
