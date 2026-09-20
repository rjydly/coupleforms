import os
import csv
import io
import time
import random
import requests
import subprocess
import html
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
TEST_MODE = False  # 🧪 Canvia a True per fer una prova sense publicar a xarxes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_QUESTION_PATH = os.path.join(BASE_DIR, 'posts.csv')
CSV_TEST_PATH = os.path.join(BASE_DIR, 'posts_test.csv')
STATE_PATH = os.path.join(BASE_DIR, 'next_post_type.txt')

SLIDES_DIR = os.path.join(BASE_DIR, 'public_slides')

FONT_SERIF_REG_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Regular.ttf')
FONT_SERIF_ITALIC_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Italic.ttf')
FONT_SANS_PATH = os.path.join(BASE_DIR, 'Poppins-Medium.ttf')

FONT_SERIF_REG_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
FONT_SERIF_ITALIC_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"
FONT_SANS_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf"

ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
ZERNIO_TIKTOK_ACCOUNT_ID = os.getenv("ZERNIO_TIKTOK_ACCOUNT_ID")
ZERNIO_INSTAGRAM_ACCOUNT_ID = os.getenv("ZERNIO_INSTAGRAM_ACCOUNT_ID")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ========================================================
# UTILITATS I HOSTING A GIT
# ========================================================

def clean_directory(dir_path):
    """Buda completament la carpeta de carrousels anteriors."""
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
    if not repo:
        return False
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

def get_public_image_urls(image_paths, run_tag):
    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if not repo:
        raise Exception("❌ Falta la variable GITHUB_REPOSITORY.")

    print(f"📤 Pujant noves diapositives al repositori de GitHub (Tag: {run_tag})...")
    commit_repo_files(["public_slides/"], f"upload: slides v{run_tag}")

    urls = []
    for f in image_paths:
        fname = os.path.basename(f)
        urls.append(f"https://raw.githubusercontent.com/{repo}/{branch}/public_slides/{fname}?v={run_tag}")
    return urls

def send_telegram_text(message):
    """Envia únicament text a Telegram per no omplir la galeria."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        requests.post(url, data=payload, timeout=20)
        print("📲 Notificació de text enviada a Telegram!")
    except Exception as e:
        print(f"⚠️ Error enviant text a Telegram: {e}")

# ========================================================
# FILTRES I DISSENY D'IMATGES (UNSPLASH)
# ========================================================

def generate_background_image():
    """Descarrega una fotografia real d'alta qualitat d'Unsplash en format quadrat (1080x1080)."""
    try:
        seed = random.randint(1, 1000000)
        url = f"https://picsum.photos/1080/1080?random={seed}"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            return Image.open(io.BytesIO(res.content)).convert('RGB')
    except Exception as e:
        print(f"⚠️ Error descarregant d'Unsplash: {e}")

    # Fons de reserva blau marí
    return Image.new('RGB', (1080, 1080), color='#2B4380')

def apply_retro_filters_and_frame(bg_img):
    img_fade = ImageEnhance.Contrast(bg_img).enhance(0.85)
    warm_matrix = (1.2, 0.2, -0.1, 0, 0.1, 1.1, -0.1, 0, 0.1, 0.1, 0.8, 0)
    img_warm = img_fade.convert('RGB', warm_matrix)
    dark_bg = ImageEnhance.Brightness(img_warm).enhance(0.42)

    width, height = 1080, 1080
    frame = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    blur_r, margin, radius = 10, 28, 60
    inner_m = margin - blur_r

    mask = Image.new('L', (width, height), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([(inner_m, inner_m), (width - inner_m, height - inner_m)], radius=radius + blur_r, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_r))

    return Image.composite(dark_bg.convert('RGBA'), frame, mask).convert('RGB')

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

def draw_title_with_underline(draw, text, highlight_word, font_title, width, start_y):
    max_w = width - 180
    lines = wrap_text(text, draw, font_title, max_w)
    line_h = [draw.textbbox((0, 0), l, font=font_title)[3] - draw.textbbox((0, 0), l, font=font_title)[1] for l in lines]
    total_h = sum(line_h) + (24 * (len(lines) - 1))
    cur_y = start_y if start_y else (1080 - total_h) / 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_w = bbox[2] - bbox[0]
        start_x = (width - line_w) / 2
        draw.text((start_x, cur_y), line, fill='#FFFFFF', font=font_title)

        if highlight_word and highlight_word.lower() in line.lower():
            idx = line.lower().find(highlight_word.lower())
            word_exact = line[idx:idx+len(highlight_word)]
            pre_text = line[:idx]
            pre_w = draw.textbbox((0, 0), pre_text, font=font_title)[2] - draw.textbbox((0, 0), pre_text, font=font_title)[0] if pre_text else 0
            word_w = draw.textbbox((0, 0), word_exact, font=font_title)[2] - draw.textbbox((0, 0), word_exact, font=font_title)[0]
            ux1, ux2 = start_x + pre_w, start_x + pre_w + word_w
            uy = cur_y + (bbox[3] - bbox[1]) + 10
            draw.line([(ux1, uy), (ux2, uy)], fill='#FFFFFF', width=4)

        cur_y += (bbox[3] - bbox[1]) + 24

def draw_question_slide(draw, text, font, width):
    lines = wrap_text(text, draw, font, 880)
    line_h = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]
    cur_y = (1080 - (sum(line_h) + (22 * (len(lines) - 1)))) / 2
    for l in lines:
        bbox = draw.textbbox((0, 0), l, font=font)
        draw.text((100, cur_y), l, fill='#FFFFFF', font=font)
        cur_y += (bbox[3] - bbox[1]) + 22

def draw_test_slide(draw, question_text, options, font_question, font_option_letter, font_option_text, width):
    lines = wrap_text(question_text, draw, font_question, 900)
    cur_y = 240
    for l in lines:
        bbox = draw.textbbox((0, 0), l, font=font_question)
        draw.text((100, cur_y), l, fill='#FFFFFF', font=font_question)
        cur_y += (bbox[3] - bbox[1]) + 16

    cur_y += 40
    for opt_letter, opt_text in options:
        if not str(opt_text).strip(): continue
        draw.text((100, cur_y), opt_letter, fill='#FFFFFF', font=font_option_letter)
        draw.text((160, cur_y), opt_text, fill='#FFFFFF', font=font_option_text)
        cur_y += 65

def draw_footer(draw, font_sans, width):
    text = "coupleforms"
    bbox = draw.textbbox((0, 0), text, font=font_sans)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) / 2, 920), text, fill=(255, 255, 255, 220), font=font_sans)

# ========================================================
# ZERNIO API
# ========================================================

def post_carousel_to_zernio(image_urls, raw_title):
    zernio_url = "https://zernio.com/api/v1/posts"
    headers = {"Authorization": f"Bearer {ZERNIO_API_KEY}", "Content-Type": "application/json"}

    clean_title = raw_title.strip()
    tiktok_title = clean_title[:87] + "..." if len(clean_title) > 90 else clean_title

    # Descripció per a TikTok (sense menció a bio)
    tiktok_description = (
        f"{clean_title}\n\n"
        "Send this to your favorite person ❤️\n"
        "Play online for free at formfriends.com (no sign-up needed)\n\n"
        "—\n#couples #relationshipgoals #couplesquestions #formfriends"
    )

    # Descripció per a Instagram (amb crida a comentar LOVE)
    instagram_content = (
        f"{clean_title}\n\n"
        "Tag your person in the comments ❤️\n\n"
        "Comment 'LOVE' and we'll DM you the link to play!\n"
        "(Online, 100% free, no sign-up needed)\n\n"
        "—\n#couples #relationshipgoals #couplesquestions #formfriends"
    )

    media_items = [{"type": "image", "url": url} for url in image_urls]

    # Configuració TikTok
    tiktok_settings_payload = {
        "privacy_level": "PUBLIC_TO_EVERYONE",
        "allow_comment": True,
        "media_type": "photo",
        "photo_cover_index": 0,
        "description": tiktok_description,
        "auto_add_music": True,
        "autoAddMusic": True,
        "content_preview_confirmed": True,
        "express_consent_given": True
    }

    # Configuració Instagram (amb comentari fixat per activar els DMs)
    instagram_platform_data = {
        "firstComment": "Follow us & comment LOVE and we'll send you the direct link! ✨ (Online, 100% free, no sign-up needed)"
    }

    payload = {
        "content": tiktok_title,
        "media_items": media_items,
        "mediaItems": media_items,
        "platforms": [
            {
                "platform": "tiktok",
                "accountId": ZERNIO_TIKTOK_ACCOUNT_ID,
                "content": tiktok_title,
                "tiktok_settings": tiktok_settings_payload,
                "tiktokSettings": tiktok_settings_payload
            },
            {
                "platform": "instagram",
                "accountId": ZERNIO_INSTAGRAM_ACCOUNT_ID,
                "content": instagram_content,
                "platformSpecificData": instagram_platform_data
            }
        ],
        "tiktok_settings": tiktok_settings_payload,
        "tiktokSettings": tiktok_settings_payload,
        "publish_now": True,
        "publishNow": True
    }

    try:
        res = requests.post(zernio_url, headers=headers, json=payload, timeout=120)
        return res.status_code in (200, 201)
    except Exception as e:
        print(f"⚠️ Error publicant carrousel a Zernio: {e}")
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
    if 'Status' not in headers: return None, None
    for r in rows:
        while len(r) < len(headers): r.append('')
    return headers, rows

def find_first_pending(headers, rows):
    status_idx = headers.index('Status')
    for idx, r in enumerate(rows):
        if r[status_idx].strip().lower() == 'pending':
            return idx, dict(zip(headers, r))
    return None, None

def write_csv_safe(csv_path, headers, rows):
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def load_next_post_type():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            v = f.read().strip().lower()
        if v in ('question', 'test'): return v
    return 'question'

def save_next_post_type(post_type):
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        f.write(post_type)

def pick_post_to_process():
    pref = load_next_post_type()
    other = 'test' if pref == 'question' else 'question'
    for post_type in (pref, other):
        csv_path = CSV_TEST_PATH if post_type == 'test' else CSV_QUESTION_PATH
        headers, rows = read_csv_safe(csv_path)
        if headers is None: continue
        idx, post_data = find_first_pending(headers, rows)
        if idx is not None:
            return post_type, csv_path, headers, rows, idx, post_data
    return None, None, None, None, None, None

# ========================================================
# MAIN
# ========================================================

def main():
    download_file(FONT_SERIF_REG_URL, FONT_SERIF_REG_PATH)
    download_file(FONT_SERIF_ITALIC_URL, FONT_SERIF_ITALIC_PATH)
    download_file(FONT_SANS_URL, FONT_SANS_PATH)

    clean_directory(SLIDES_DIR)

    post_type, csv_path, headers, rows, current_idx, post_data = pick_post_to_process()
    if post_type is None:
        print("🎉 Tots els carrousels estan completats ('Done')!")
        return

    RUN_TAG = int(time.time())
    status_idx = headers.index('Status')
    post_id = post_data.get('Post_ID', f"Post_{current_idx + 1}")
    raw_title = post_data.get('Slide_1_Title', '')

    print(f"🚀 Generant Carrousel {post_id} ({post_type}) amb Tag: {RUN_TAG}...")

    font_serif_large = ImageFont.truetype(FONT_SERIF_REG_PATH, 58)
    font_serif_med = ImageFont.truetype(FONT_SERIF_REG_PATH, 46)
    font_serif_italic = ImageFont.truetype(FONT_SERIF_ITALIC_PATH, 44)
    font_sans_footer = ImageFont.truetype(FONT_SANS_PATH, 28)

    temp_files = []

    for i in range(6):
        base_bg = generate_background_image()
        s = apply_retro_filters_and_frame(base_bg)
        d = ImageDraw.Draw(s)

        if i == 0:
            draw_title_with_underline(d, raw_title, post_data.get('Highlight_Word', ''), font_serif_large, 1080, None)
        elif post_type == 'test':
            q_text = post_data.get(f'Slide_{i+1}_Question', '')
            options = [
                ('A) ', post_data.get(f'Slide_{i+1}_OptA', '')),
                ('B) ', post_data.get(f'Slide_{i+1}_OptB', '')),
                ('C) ', post_data.get(f'Slide_{i+1}_OptC', '')),
                ('D) ', post_data.get(f'Slide_{i+1}_OptD', '')),
            ]
            draw_test_slide(d, q_text, options, font_serif_med, font_serif_italic, font_serif_med, 1080)
        else:
            key = 'Slide_2_Question_or_Title' if i == 1 else f'Slide_{i+1}_Question'
            draw_question_slide(d, post_data.get(key, ''), font_serif_med, 1080)

        draw_footer(d, font_sans_footer, 1080)

        f_path = os.path.join(SLIDES_DIR, f"{post_id}_v{RUN_TAG}_s{i+1}.jpg")
        s.save(f_path, "JPEG", quality=95)
        temp_files.append(f_path)

    rows[current_idx][status_idx] = 'Done'
    write_csv_safe(csv_path, headers, rows)

    next_type = 'test' if post_type == 'question' else 'question'
    save_next_post_type(next_type)

    csv_relpath = os.path.relpath(csv_path, BASE_DIR)
    state_relpath = os.path.relpath(STATE_PATH, BASE_DIR)

    public_urls = get_public_image_urls(temp_files, RUN_TAG)

    if TEST_MODE:
        msg = (
            f"🧪 <b>[MODE PROVA - CARROUSEL]</b>\n\n"
            f"📌 <b>ID:</b> {post_id} ({post_type})\n"
            f"🏷️ <b>Tag Cache:</b> {RUN_TAG}\n"
            f"📖 <b>Títol:</b> {html.escape(raw_title)}\n\n"
            f"🔗 <b>Enllaç Slide 1:</b>\n{public_urls[0]}"
        )
        send_telegram_text(msg)
        commit_repo_files([csv_relpath, state_relpath], f"chore: {post_id} -> Done (mode prova)")
    else:
        if not ZERNIO_API_KEY: raise Exception("⚠️ Falta ZERNIO_API_KEY.")

        if post_carousel_to_zernio(public_urls, raw_title):
            msg = (
                f"🚀 <b>Carrousel Publicat! (TikTok + Instagram)</b>\n\n"
                f"📌 <b>ID:</b> {post_id} ({post_type})\n"
                f"🏷️ <b>Tag Cache:</b> {RUN_TAG}\n"
                f"📖 <b>Títol:</b> {html.escape(raw_title)}\n\n"
                f"🔗 <b>Enllaç Slide 1:</b>\n{public_urls[0]}"
            )
            send_telegram_text(msg)

        commit_repo_files([csv_relpath, state_relpath], f"chore: {post_id} -> Done ({post_type})")

    print(f"📝 Procés completat! Proper carrousel: {next_type}")

if __name__ == "__main__":
    main()
