import os
import csv
import io
import json
import random
import requests
import ftplib
import subprocess
import html
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# Integració oficial amb Google AI Studio
from google import genai
from google.genai import types

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
TEST_MODE = True  # 🧪 Canvia a False per publicar realment a Buffer / Xarxes socials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'posts.csv')
SLIDES_DIR = os.path.join(BASE_DIR, 'public_slides')

# Fonts elegants estil Serif (Playfair Display) i Sans (Poppins)
FONT_SERIF_REG_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Regular.ttf')
FONT_SERIF_BOLD_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Bold.ttf')
FONT_SERIF_ITALIC_PATH = os.path.join(BASE_DIR, 'PlayfairDisplay-Italic.ttf')
FONT_SANS_PATH = os.path.join(BASE_DIR, 'Poppins-Medium.ttf')

FONT_SERIF_REG_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
FONT_SERIF_ITALIC_URL = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"
FONT_SANS_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf"

# ENVS
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Clau de Google AI Studio

FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")

# Prompts estrictament SENSE PERSONES (Només paisatges i espais)
PROMPT_POOL = [
    "completely empty scenic landscape, quiet sunset over calm ocean, vintage 35mm film photograph, warm golden hour, soft film grain, deserted, no humans, no people, no silhouettes",
    "empty cozy balcony overlooking a serene lake at twilight, warm dim fairy lights, retro 35mm analog photo, vintage muted tones, no people, no humans",
    "peaceful autumn forest landscape with soft sunlight through trees, vintage Kodachrome photograph, warm retro colors, empty nature view, no people",
    "deserted cobblestone alley in a European village at dusk, architecture only, warm street lamps glow, 35mm analog film texture, completely empty, no people, no silhouettes",
    "serene mountain reflection on a quiet lake at sunrise, retro 35mm aesthetic, soft warm glow, untouched nature landscape, empty scenery, no humans"
]

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

    # 3. Fosc per garantir la llegibilitat del text blanc (50% de brillantor)
    brightness_enhancer = ImageEnhance.Brightness(img_warm)
    dark_bg = brightness_enhancer.enhance(0.50)

    # 4. Marc exterior fosc amb cantonades arrodonides
    width, height = 1080, 1080
    frame = Image.new('RGBA', (width, height), (10, 12, 18, 255))
    
    mask = Image.new('L', (width, height), 0)
    draw_mask = ImageDraw.Draw(mask)
    
    margin = 40
    radius = 70
    draw_mask.rounded_rectangle(
        [(margin, margin), (width - margin, height - margin)],
        radius=radius, fill=255
    )

    dark_bg_rgba = dark_bg.convert('RGBA')
    final_canvas = Image.composite(dark_bg_rgba, frame, mask)
    
    # Vignette interior suau
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rounded_rectangle(
        [(margin, margin), (width - margin, height - margin)],
        radius=radius, outline=(0, 0, 0, 90), width=6
    )
    
    return Image.alpha_composite(final_canvas, overlay).convert('RGB')

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

def draw_footer(draw, font_sans, width):
    """Marca d'aigua inferior discreta"""
    text = "formfriends"
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
        try:
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
            subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
            subprocess.run(["git", "add", "public_slides/"], check=True)
            subprocess.run(["git", "commit", "-m", "upload: slides"], check=False)
            subprocess.run(["git", "push"], check=False)
        except: pass
        return [f"https://raw.githubusercontent.com/{repo}/{branch}/public_slides/{os.path.basename(f)}" for f in temp_files]

    raise Exception("❌ Sense URL pública.")

def post_to_buffer(token, image_urls, caption):
    buffer_url = "https://api.buffer.com"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    org_res = requests.post(buffer_url, headers=headers, json={"query": "query { account { organizations { id } } }"})
    orgs = org_res.json().get("data", {}).get("account", {}).get("organizations", [])
    if not orgs: return False
    
    ch_res = requests.post(buffer_url, headers=headers, json={
        "query": "query GetChannels($input: ChannelsInput!) { channels(input: $input) { id service displayName } }",
        "variables": {"input": {"organizationId": orgs[0]["id"]}}
    })
    channels = ch_res.json().get("data", {}).get("channels", [])
    
    assets = [{"image": {"url": url}} for url in image_urls]
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """
    
    success = True
    for ch in channels:
        service = str(ch.get("service", "")).lower()
        if "youtube" in service: continue
        
        inp = {
            "channelId": ch["id"],
            "text": caption,
            "schedulingType": "automatic",
            "mode": "shareNow",
            "assets": assets
        }
        if "instagram" in service:
            inp["metadata"] = {"instagram": {"type": "post", "shouldShareToFeed": True}}
            
        res = requests.post(buffer_url, headers=headers, json={"query": mutation, "variables": {"input": inp}})
        if "errors" in res.json(): success = False
        
    return success

def main():
    download_file(FONT_SERIF_REG_URL, FONT_SERIF_REG_PATH)
    download_file(FONT_SERIF_ITALIC_URL, FONT_SERIF_ITALIC_PATH)
    download_file(FONT_SANS_URL, FONT_SANS_PATH)
    
    os.makedirs(SLIDES_DIR, exist_ok=True)
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: Fitxer CSV no trobat a {CSV_PATH}")
        return

    # LECTURA SEGURA DEL CSV
    rows, headers = [], []
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            print("❌ Error: El fitxer CSV està buit.")
            return
            
        for r in reader:
            if r and any(field.strip() for field in r):
                rows.append(r)

    if 'Status' not in headers:
        print("❌ Error: No s'ha trobat la columna 'Status' al CSV.")
        return

    status_idx = headers.index('Status')
    current_idx, post_data = None, None
    
    for idx, r in enumerate(rows):
        while len(r) < len(headers):
            r.append('')
            
        if r[status_idx].strip().lower() == 'pending':
            current_idx = idx
            post_data = dict(zip(headers, r))
            break

    if current_idx is None:
        print("🎉 Tots els posts del CSV estan completats ('Done')!")
        return

    post_id = post_data.get('Post_ID', f"Post_{current_idx + 1}")
    post_type = post_data.get('Type', 'Question')
    print(f"🚀 Generant carrousel ({post_type}) per a {post_id} (MODE PROVA = {TEST_MODE})...")

    # Carregar Fonts
    font_serif_large = ImageFont.truetype(FONT_SERIF_REG_PATH, 58)
    font_serif_med = ImageFont.truetype(FONT_SERIF_REG_PATH, 46)
    font_serif_italic = ImageFont.truetype(FONT_SERIF_ITALIC_PATH, 44)
    font_sans_footer = ImageFont.truetype(FONT_SANS_PATH, 28)

    temp_files = []

    # --- GENERACIÓ DE LES 6 DIAPOSITIVES AMB FONTS INDEPENDENTS ---
    slide_keys = [
        'Slide_1_Title',
        'Slide_2_Question_or_Title',
        'Slide_3_Question',
        'Slide_4_Question',
        'Slide_5_Question',
        'Slide_6_Question'
    ]

    for i, key in enumerate(slide_keys):
        print(f"🖼️ Generant fons retro per a la Slide {i+1}/6...")
        base_bg = generate_background_image()
        s = apply_retro_filters_and_frame(base_bg)
        d = ImageDraw.Draw(s)
        
        if i == 0:
            # --- SLIDE 1: PORTADA ---
            draw_title_with_underline(d, post_data.get('Slide_1_Title', ''), post_data.get('Highlight_Word', ''), font_serif_large, 1080, None)
        elif i == 1 and post_type.lower() == 'test':
            # --- SLIDE 2: TEST (Opcions A, B, C, D) ---
            q_text = post_data.get('Slide_2_Question_or_Title', '')
            options = [
                ('A) ', post_data.get('Option_A', '')),
                ('B) ', post_data.get('Option_B', '')),
                ('C) ', post_data.get('Option_C', '')),
                ('D) ', post_data.get('Option_D', ''))
            ]
            
            lines = wrap_text(q_text, d, font_serif_med, 900)
            y_curr = 240
            for l in lines:
                bbox = d.textbbox((0, 0), l, font=font_serif_med)
                d.text((100, y_curr), l, fill='#FFFFFF', font=font_serif_med)
                y_curr += (bbox[3] - bbox[1]) + 16
            
            y_curr += 40
            for opt_letter, opt_text in options:
                if not opt_text.strip(): continue
                d.text((100, y_curr), opt_letter, fill='#FFFFFF', font=font_serif_italic)
                d.text((160, y_curr), opt_text, fill='#FFFFFF', font=font_serif_med)
                y_curr += 65
        else:
            # --- SLIDES 2 A 6: PREGUNTES ESTÀNDARD ---
            q_text = post_data.get(key, '')
            lines = wrap_text(q_text, d, font_serif_med, 880)
            line_heights = [d.textbbox((0, 0), l, font=font_serif_med)[3] - d.textbbox((0, 0), l, font=font_serif_med)[1] for l in lines]
            total_h = sum(line_heights) + (22 * (len(lines) - 1))
            
            y_curr = (1080 - total_h) / 2
            for l in lines:
                bbox = d.textbbox((0, 0), l, font=font_serif_med)
                d.text((100, y_curr), l, fill='#FFFFFF', font=font_serif_med)
                y_curr += (bbox[3] - bbox[1]) + 22
                
        draw_footer(d, font_sans_footer, 1080)
        
        f_path = os.path.join(SLIDES_DIR, f"{post_id}_slide_{i+1}.jpg")
        s.save(f_path, "JPEG", quality=95)
        temp_files.append(f_path)

    tags = "#couples #relationshipgoals #deepquestions #couplesgame #formfriends"
    caption = f"{post_data.get('Slide_1_Title', '')}\n\nTag your person and answer in the comments. ✨\n\nLink in bio to play formfriends.com\n\n—\n{tags}"

    if TEST_MODE:
        # ========================================================
        # MODE PROVA: NOMÉS ENVIAMENT A TELEGRAM
        # ========================================================
        print("🧪 MODE PROVA ACTIVAT: S'omet Buffer. Enviant les 6 imatges a Telegram...")
        title_text = html.escape(post_data.get('Slide_1_Title', ''))
        telegram_msg = (
            f"🧪 <b>[MODE PROVA] {post_id} generat ({post_type})</b>\n\n"
            f"📖 <b>Títol:</b> {title_text}\n"
            f"🏷️ <b>Hashtags:</b> {tags}\n\n"
            f"<i>No s'ha enviat a Buffer. Comprova les 6 diapositives a l'àlbum adjunt!</i>"
        )
        send_telegram_media_group(telegram_msg, temp_files)

        rows[current_idx][status_idx] = 'Done'
        with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"📝 CSV actualitzat (Mode Prova)! {post_id} -> Done.")

    else:
        # ========================================================
        # MODE PRODUCCIÓ: PUBLICACIÓ A BUFFER
        # ========================================================
        if not BUFFER_ACCESS_TOKEN:
            print("⚠️ BUFFER_ACCESS_TOKEN no configurat.")
            return

        public_urls = get_public_image_urls(temp_files)
        print("📤 Enviant carrousel a Buffer...")
        
        if post_to_buffer(BUFFER_ACCESS_TOKEN, public_urls, caption):
            telegram_msg = f"🚀 <b>{post_id} publicat amb èxit!</b>\n\n📖 {html.escape(post_data.get('Slide_1_Title', ''))}"
            send_telegram_media_group(telegram_msg, temp_files)
            
            rows[current_idx][status_idx] = 'Done'
            with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            print(f"📝 CSV actualitzat! {post_id} -> Done.")

if __name__ == "__main__":
    main()
