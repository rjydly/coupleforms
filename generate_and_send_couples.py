import os
import csv
import io
import json
import random
import requests
import ftplib
import subprocess
import html
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

# Integració oficial amb Google AI Studio
from google import genai
from google.genai import types

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
TEST_MODE = False  # 🧪 Canvia a False per publicar realment a Zernio (TikTok + Instagram)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dos fitxers CSV independents, cadascun amb el seu propi esquema:
#  - posts.csv       -> posts 'Question' (5 preguntes normals, sense opcions)
#  - posts_test.csv  -> posts 'Test' (5 preguntes, cadascuna amb 4 opcions A-D)
CSV_QUESTION_PATH = os.path.join(BASE_DIR, 'posts.csv')
CSV_TEST_PATH = os.path.join(BASE_DIR, 'posts_test.csv')

# Fitxer d'estat que recorda quin tipus de post toca la propera vegada,
# per poder intercalar Question / Test entre execucions consecutives del workflow.
STATE_PATH = os.path.join(BASE_DIR, 'next_post_type.txt')

SLIDES_DIR = os.path.join(BASE_DIR, 'public_slides')

# Fonts elegants estil Serif (Playfair Display) i Sans (Poppins)
FONT_SERIF_REG_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Regular.ttf')
FONT_SERIF_BOLD_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Bold.ttf')
FONT_SERIF_ITALIC_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Italic.ttf')
FONT_SANS_PATH = os.path.join(BASE_DIR, 'Poppins-Medium.ttf')

FONT_SERIF_REG_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
FONT_SERIF_ITALIC_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"
FONT_SANS_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf"

# ENVS (Claus d'API i IDs de compte)
ZERNIO_API_KEY = os.getenv("ZERNIO_API_KEY")
ZERNIO_TIKTOK_ACCOUNT_ID = os.getenv("ZERNIO_TIKTOK_ACCOUNT_ID")
ZERNIO_INSTAGRAM_ACCOUNT_ID = os.getenv("ZERNIO_INSTAGRAM_ACCOUNT_ID")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Clau de Google AI Studio

FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")

# Prompts strictly SENSE PERSONES (Només paisatges i espais)
PROMPT_POOL = [
    "completely empty scenic landscape, quiet sunset over calm ocean, vintage 35mm film photograph, warm golden hour, soft film grain, deserted, no humans, no people, no silhouettes",
    "empty cozy balcony overlooking a serene lake at twilight, warm dim fairy lights, retro 35mm analog photo, vintage muted tones, no people, no humans",
    "peaceful autumn forest landscape with soft sunlight through trees, vintage Kodachrome photograph, warm retro colors, empty nature view, no people",
    "deserted cobblestone alley in a European village at dusk, architecture only, warm street lamps glow, 35mm analog film texture, completely empty, no people, no silhouettes",
    "serene mountain reflection on a quiet lake at sunrise, retro 35mm aesthetic, soft warm glow, untouched nature landscape, empty scenery, no humans"
]

# ========================================================
# UTILITATS GENERALS
# ========================================================

def download_file(url, save_path):
    if not os.path.exists(save_path):
        print(f"📥 Descarregant: {os.path.basename(save_path)}...")
        res = requests.get(url)
        with open(save_path, 'wb') as f:
            f.write(res.content)

def generate_background_image():
    """Genera una imatge de paisatge 1080x1080 via Google AI Studio (Imagen 3)"""
    prompt = random.choice(PROMPT_POOL)

    if GEMINI_API_KEY:
        try:
            print("🎨 Generant nova imatge de paisatge via Google AI Studio (Imagen 3)...")
            client = genai.Client(api_key=GEMINI_API_KEY)

            response = client.models.generate_images(
                model='imagen-3.0-generate-002',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type='image/jpeg',
                    aspect_ratio='1:1',
                    negative_prompt='people, human, person, silhouette, faces, crowds'
                )
            )

            if response.generated_images:
                img_bytes = response.generated_images[0].image.image_bytes
                img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                img = img.resize((1080, 1080), Image.Resampling.LANCZOS)
                print("✅ Imatge generada amb èxit via Google AI Studio!")
                return img

        except Exception as e:
            print(f"⚠️ Error a Google AI Studio: {e}. Intentant fallback...")

    # Fallback 1: Imatge real de paisatge d'alta qualitat (Unsplash)
    try:
        print("📷 Carregant paisatge d'alta qualitat des d'Unsplash...")
        unsplash_url = "https://picsum.photos/1080/1080"
        res = requests.get(unsplash_url, timeout=15)
        if res.status_code == 200:
            img = Image.open(io.BytesIO(res.content)).convert('RGB')
            print("✅ Paisatge descarregat d'Unsplash!")
            return img
    except Exception as e:
        print(f"⚠️ Error Unsplash: {e}")

    # Fallback 2: Fons blau retro
    print("🎨 Usant fons de reserva blau retro...")
    return Image.new('RGB', (1080, 1080), color='#2B4380')

def apply_retro_filters_and_frame(bg_img):
    """Aplica filtre retro càlid, baixada de contrast, foscor i el marc arrodonit"""
    # 1. Reduir contrast per a un efecte desteñit/vell
    contrast_enhancer = ImageEnhance.Contrast(bg_img)
    img_fade = contrast_enhancer.enhance(0.85)

    # 2. Aplicar to càlid/sepia utilitzant la matriu de transformació de color
    warm_matrix = (
        1.2, 0.2, -0.1, 0,
        0.1, 1.1, -0.1, 0,
        0.1, 0.1,  0.8, 0
    )
    img_warm = img_fade.convert('RGB', warm_matrix)

    # 3. Fosc per garantir la llegibilitat del text blanc
    brightness_enhancer = ImageEnhance.Brightness(img_warm)
    dark_bg = brightness_enhancer.enhance(0.42)

    # 4. Marc exterior 100% negre amb un blackfade estret a la vora
    width, height = 1080, 1080
    frame = Image.new('RGBA', (width, height), (0, 0, 0, 255))

    blur_r   = 10   # radi de difuminat
    margin   = 28   # vora negra visible
    radius   = 60   # arrodoniment de cantonades
    inner_m  = margin - blur_r

    mask = Image.new('L', (width, height), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle(
        [(inner_m, inner_m), (width - inner_m, height - inner_m)],
        radius=radius + blur_r, fill=255
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_r))

    dark_bg_rgba = dark_bg.convert('RGBA')
    final_canvas = Image.composite(dark_bg_rgba, frame, mask)

    return final_canvas.convert('RGB')

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

def draw_title_with_underline(draw, text, highlight_word, font_title, width, start_y):
    """Dibuixa el títol centrat i subratlla la paraula destacada"""
    max_w = width - 180
    lines = wrap_text(text, draw, font_title, max_w)

    line_heights = [draw.textbbox((0, 0), l, font=font_title)[3] - draw.textbbox((0, 0), l, font=font_title)[1] for l in lines]
    total_h = sum(line_heights) + (24 * (len(lines) - 1))

    current_y = start_y if start_y else (1080 - total_h) / 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_w = bbox[2] - bbox[0]
        start_x = (width - line_w) / 2

        draw.text((start_x, current_y), line, fill='#FFFFFF', font=font_title)

        if highlight_word and highlight_word.lower() in line.lower():
            idx = line.lower().find(highlight_word.lower())
            word_exact = line[idx:idx+len(highlight_word)]

            pre_text = line[:idx]
            pre_w = draw.textbbox((0, 0), pre_text, font=font_title)[2] - draw.textbbox((0, 0), pre_text, font=font_title)[0] if pre_text else 0

            word_w = draw.textbbox((0, 0), word_exact, font=font_title)[2] - draw.textbbox((0, 0), word_exact, font=font_title)[0]

            ux1 = start_x + pre_w
            ux2 = ux1 + word_w
            uy = current_y + (bbox[3] - bbox[1]) + 10

            draw.line([(ux1, uy), (ux2, uy)], fill='#FFFFFF', width=4)

        current_y += (bbox[3] - bbox[1]) + 24

def draw_question_slide(draw, text, font, width):
    """Dibuixa una diapositiva de pregunta normal (sense opcions), centrada verticalment"""
    lines = wrap_text(text, draw, font, 880)
    line_heights = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]
    total_h = sum(line_heights) + (22 * (len(lines) - 1))

    y_curr = (1080 - total_h) / 2
    for l in lines:
        bbox = draw.textbbox((0, 0), l, font=font)
        draw.text((100, y_curr), l, fill='#FFFFFF', font=font)
        y_curr += (bbox[3] - bbox[1]) + 22

def draw_test_slide(draw, question_text, options, font_question, font_option_letter, font_option_text, width):
    """Dibuixa una diapositiva de tipus Test: pregunta + fins a 4 opcions (A-D)"""
    lines = wrap_text(question_text, draw, font_question, 900)
    y_curr = 240
    for l in lines:
        bbox = draw.textbbox((0, 0), l, font=font_question)
        draw.text((100, y_curr), l, fill='#FFFFFF', font=font_question)
        y_curr += (bbox[3] - bbox[1]) + 16

    y_curr += 40
    for opt_letter, opt_text in options:
        if not str(opt_text).strip():
            continue
        draw.text((100, y_curr), opt_letter, fill='#FFFFFF', font=font_option_letter)
        draw.text((160, y_curr), opt_text, fill='#FFFFFF', font=font_option_text)
        y_curr += 65

def draw_footer(draw, font_sans, width):
    """Marca d'aigua inferior discreta"""
    text = "coupleforms"
    bbox = draw.textbbox((0, 0), text, font=font_sans)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) / 2, 920), text, fill=(255, 255, 255, 220), font=font_sans)

def send_telegram_media_group(message, photo_paths):
    """Envia l'àlbum de fotos complet (les 6 diapositives) a Telegram per a la revisió"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram no configurat.")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'})

        media = []
        files = {}
        for idx, path in enumerate(photo_paths):
            file_key = f"photo_{idx}"
            media.append({"type": "photo", "media": f"attach://{file_key}"})
            files[file_key] = open(path, 'rb')

        payload = {'chat_id': TELEGRAM_CHAT_ID, 'media': json.dumps(media)}
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup", data=payload, files=files)
        print("📲 Àlbum complet de slides enviat a Telegram!")
    except Exception as e:
        print(f"⚠️ Error enviant àlbum a Telegram: {e}")

def upload_via_ftp(file_path):
    if not (FTP_HOST and FTP_USER and FTP_PASS):
        return None
    filename = os.path.basename(file_path)
    try:
        ftp = ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASS, timeout=30)
        try: ftp.cwd("public_html")
        except: pass
        try: ftp.cwd("public_slides")
        except:
            ftp.mkd("public_slides")
            ftp.cwd("public_slides")
        with open(file_path, 'rb') as f:
            ftp.storbinary(f'STOR {filename}', f)
        ftp.quit()
        return f"https://formfriends.com/public_slides/{filename}"
    except Exception as e:
        print(f"⚠️ Error FTP: {e}")
        return None

def get_public_image_urls(temp_files):
    if FTP_HOST and FTP_USER and FTP_PASS:
        urls = [upload_via_ftp(f) for f in temp_files]
        if all(urls): return urls

    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if repo:
        commit_repo_files(["public_slides/"], "upload: slides")
        return [f"https://raw.githubusercontent.com/{repo}/{branch}/public_slides/{os.path.basename(f)}" for f in temp_files]

    raise Exception("❌ Sense URL pública.")

def commit_repo_files(paths, message):
    """Fa `git add` només dels paths indicats, commit i push."""
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        print("ℹ️ No s'ha detectat GITHUB_REPOSITORY: s'omet el commit (execució local).")
        return False
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add"] + list(paths), check=True)
        commit_res = subprocess.run(["git", "commit", "-m", message], check=False)
        subprocess.run(["git", "push"], check=False)
        return commit_res.returncode == 0
    except Exception as e:
        print(f"⚠️ Error fent commit/push: {e}")
        return False

def post_to_zernio(api_key, tiktok_account_id, instagram_account_id, image_urls, title, caption):
    """Publica un carrousel d'imatges immediatament a TikTok i Instagram via Zernio API."""
    
    if not image_urls:
        print("❌ Error: La llista d'URLs d'imatges està buida.")
        return False

    zernio_url = "https://zernio.com/api/v1/posts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    clean_title = title.strip()

    # 1. TikTok Photo Mode només admet un màxim de 90 caràcters
    if len(clean_title) > 90:
        tiktok_content = clean_title[:87] + "..."
    else:
        tiktok_content = clean_title

    # 2. Instagram admet text llarg (Títol + Descripció + Hashtags)
    instagram_content = f"{clean_title}\n\n{caption}"

    media_items = [{"type": "image", "url": url} for url in image_urls]

    payload = {
        "platforms": [
            {
                "platform": "tiktok",
                "accountId": tiktok_account_id,
                "content": tiktok_content  # 👈 Text curt per a TikTok (<= 90 caràcters)
            },
            {
                "platform": "instagram",
                "accountId": instagram_account_id,
                "content": instagram_content  # 👈 Text complet per a Instagram
            }
        ],
        "content": tiktok_content,  # 👈 Fallback global integrat per passar la validació de TikTok
        "mediaItems": media_items,
        "publishNow": True,
        "tiktok_options": {
            "auto_add_music": True
        }
    }

    try:
        response = requests.post(zernio_url, headers=headers, json=payload, timeout=30)
        if response.status_code in (200, 201):
            print("✅ Carrousel enviat i publicat amb èxit a Zernio (TikTok + Instagram)!")
            return True
        else:
            print(f"❌ Error en publicar a Zernio ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ Excepció en comunicar amb Zernio: {e}")
        return False
    
# ========================================================
# LECTURA DE CSV I ALTERNANÇA DE TIPUS DE POST
# ========================================================

def read_csv_safe(csv_path):
    if not os.path.exists(csv_path):
        print(f"❌ Error: Fitxer CSV no trobat a {csv_path}")
        return None, None

    rows, headers = [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            print(f"❌ Error: El fitxer {csv_path} està buit.")
            return None, None

        for r in reader:
            if r and any(field.strip() for field in r):
                rows.append(r)

    if 'Status' not in headers:
        print(f"❌ Error: No s'ha trobat la columna 'Status' a {csv_path}.")
        return None, None

    for r in rows:
        while len(r) < len(headers):
            r.append('')

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
            value = f.read().strip().lower()
        if value in ('question', 'test'):
            return value
    return 'question'

def save_next_post_type(post_type):
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        f.write(post_type)

def pick_post_to_process():
    preferred_type = load_next_post_type()
    other_type = 'test' if preferred_type == 'question' else 'question'

    for post_type in (preferred_type, other_type):
        csv_path = CSV_TEST_PATH if post_type == 'test' else CSV_QUESTION_PATH
        headers, rows = read_csv_safe(csv_path)
        if headers is None:
            continue
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

    os.makedirs(SLIDES_DIR, exist_ok=True)

    post_type, csv_path, headers, rows, current_idx, post_data = pick_post_to_process()

    if post_type is None:
        print("🎉 Tots els posts d'ambdós CSV estan completats ('Done')!")
        return

    status_idx = headers.index('Status')
    post_id = post_data.get('Post_ID', f"Post_{current_idx + 1}")
    print(f"🚀 Generant carrousel ({post_type}) per a {post_id} des de {os.path.basename(csv_path)} (MODE PROVA = {TEST_MODE})...")

    # Carregar Fonts
    font_serif_large = ImageFont.truetype(FONT_SERIF_REG_PATH, 58)
    font_serif_med = ImageFont.truetype(FONT_SERIF_REG_PATH, 46)
    font_serif_italic = ImageFont.truetype(FONT_SERIF_ITALIC_PATH, 44)
    font_sans_footer = ImageFont.truetype(FONT_SANS_PATH, 28)

    temp_files = []

    # --- GENERACIÓ DE LES 6 DIAPOSITIVES AMB FONTS INDEPENDENTS ---
    for i in range(6):
        print(f"🖼️ Generant fons retro per a la Slide {i+1}/6...")
        base_bg = generate_background_image()
        s = apply_retro_filters_and_frame(base_bg)
        d = ImageDraw.Draw(s)

        if i == 0:
            # --- SLIDE 1: PORTADA (comuna a tots dos esquemes) ---
            draw_title_with_underline(d, post_data.get('Slide_1_Title', ''), post_data.get('Highlight_Word', ''), font_serif_large, 1080, None)

        elif post_type == 'test':
            # --- SLIDES 2-6: TEST, cadascuna amb la seva pròpia pregunta + opcions A-D ---
            q_text = post_data.get(f'Slide_{i+1}_Question', '')
            options = [
                ('A) ', post_data.get(f'Slide_{i+1}_OptA', '')),
                ('B) ', post_data.get(f'Slide_{i+1}_OptB', '')),
                ('C) ', post_data.get(f'Slide_{i+1}_OptC', '')),
                ('D) ', post_data.get(f'Slide_{i+1}_OptD', '')),
            ]
            draw_test_slide(d, q_text, options, font_serif_med, font_serif_italic, font_serif_med, 1080)

        else:
            # --- SLIDES 2-6: QUESTION, preguntes normals sense opcions ---
            key = 'Slide_2_Question_or_Title' if i == 1 else f'Slide_{i+1}_Question'
            q_text = post_data.get(key, '')
            draw_question_slide(d, q_text, font_serif_med, 1080)

        draw_footer(d, font_sans_footer, 1080)

        f_path = os.path.join(SLIDES_DIR, f"{post_id}_slide_{i+1}.jpg")
        s.save(f_path, "JPEG", quality=95)
        temp_files.append(f_path)

    raw_title = post_data.get('Slide_1_Title', '')
    tags = "#couples #relationshipgoals #deepquestions #couplesgame #formfriends"
    description = f"Tag your person and answer in the comments. ✨\n\nLink in bio to play formfriends.com\n\n—\n{tags}"

    # Marquem la fila com a 'Done' i l'escrivim sempre, independentment del mode,
    # perquè el següent run (test o producció) no la torni a agafar.
    rows[current_idx][status_idx] = 'Done'
    write_csv_safe(csv_path, headers, rows)

    # Alternem el tipus per a la propera execució.
    next_type = 'test' if post_type == 'question' else 'question'
    save_next_post_type(next_type)

    csv_relpath = os.path.relpath(csv_path, BASE_DIR)
    state_relpath = os.path.relpath(STATE_PATH, BASE_DIR)

    if TEST_MODE:
        # ========================================================
        # MODE PROVA: NOMÉS ENVIAMENT A TELEGRAM
        # ========================================================
        print("🧪 MODE PROVA ACTIVAT: S'omet Zernio. Enviant les 6 imatges a Telegram...")
        title_text = html.escape(raw_title)
        telegram_msg = (
            f"🧪 <b>[MODE PROVA] {post_id} generat ({post_type})</b>\n\n"
            f"📖 <b>Títol:</b> {title_text}\n"
            f"🏷️ <b>Hashtags:</b> {tags}\n\n"
            f"<i>No s'ha enviat a Zernio. Comprova les 6 diapositives a l'àlbum adjunt!</i>"
        )
        send_telegram_media_group(telegram_msg, temp_files)

        # Persistim SEMPRE el canvi d'Status i l'estat d'alternança al repositori
        commit_repo_files([csv_relpath, state_relpath], f"chore: {post_id} -> Done (mode prova, {post_type})")
        print(f"📝 CSV actualitzat (Mode Prova)! {post_id} -> Done. Proper tipus: {next_type}.")

    else:
        # ========================================================
        # MODE PRODUCCIÓ: PUBLICACIÓ A ZERNIO (TIKTOK + INSTAGRAM)
        # ========================================================
        if not ZERNIO_API_KEY or not ZERNIO_TIKTOK_ACCOUNT_ID or not ZERNIO_INSTAGRAM_ACCOUNT_ID:
            print("⚠️ Faltan claus o Account IDs de Zernio per configurar.")
            return

        public_urls = get_public_image_urls(temp_files)
        print("📤 Enviant carrousel a Zernio (TikTok + Instagram)...")

        if post_to_zernio(ZERNIO_API_KEY, ZERNIO_TIKTOK_ACCOUNT_ID, ZERNIO_INSTAGRAM_ACCOUNT_ID, public_urls, raw_title, description):
            telegram_msg = f"🚀 <b>{post_id} publicat amb èxit a TikTok i Instagram!</b>\n\n📖 {html.escape(raw_title)}"
            send_telegram_media_group(telegram_msg, temp_files)

        commit_repo_files([csv_relpath, state_relpath], f"chore: {post_id} -> Done ({post_type})")
        print(f"📝 CSV actualitzat! {post_id} -> Done. Proper tipus: {next_type}.")

if __name__ == "__main__":
    main()
