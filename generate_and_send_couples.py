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
HF_TOKEN = os.getenv("HF_TOKEN")  # Secret de Hugging Face

FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")

# Model de Hugging Face
HF_MODEL_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"

# Prompts per generar imatges retro de parelles/romàntiques sense persones
PROMPT_POOL = [
    "cinematic retro 35mm film photograph, cozy romantic sunset view over quiet beach, vintage warm tones, subtle film grain, soft focus, minimal aesthetic, no people",
    "analog 35mm film photo, cozy aesthetic coffee shop window on a rainy day, warm dim lighting, retro vintage color palette, soft glow, no people",
    "vintage 35mm photograph, romantic european cobblestone street at dusk, golden hour lighting, analog film grain, dreamlike atmosphere, no people",
    "cozy aesthetic balcony with fairy lights over scenic city skyline at twilight, 35mm film texture, warm muted colors, retro aesthetic, no people",
    "retro Kodachrome photograph, serene mountain lake view during golden hour sunrise, warm vintage glow, soft focus, minimal background, no people"
]

def download_file(url, save_path):
    if not os.path.exists(save_path):
        print(f"📥 Descarregant: {os.path.basename(save_path)}...")
        res = requests.get(url)
        with open(save_path, 'wb') as f:
            f.write(res.content)

def generate_hf_background():
    """Genera una imatge fons estil retro 35mm utilitzant Hugging Face API"""
    prompt = random.choice(PROMPT_POOL)
    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    
    payload = {
        "inputs": prompt,
        "parameters": {"width": 1080, "height": 1080}
    }
    
    try:
        print("🎨 Generant imatge retro via Hugging Face FLUX.1-schnell...")
        response = requests.post(HF_MODEL_URL, headers=headers, json=payload, timeout=45)
        if response.status_code == 200:
            img = Image.open(io.BytesIO(response.content)).convert('RGB')
            img = img.resize((1080, 1080), Image.Resampling.LANCZOS)
            return img
        else:
            print(f"⚠️ Error HF API ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ Error generant imatge HF: {e}")

    # Fallback: Fons degradat blau retro si l'API falla
    bg = Image.new('RGB', (1080, 1080), color='#2B4380')
    return bg

def apply_retro_frame_and_overlay(bg_img):
    """Aplica el marc exterior fosca estil TV/Càmera retro i redueix brillantor"""
    enhancer = ImageEnhance.Brightness(bg_img)
    dark_bg = enhancer.enhance(0.55)  # Baixar brillantor al 55%

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
        # 1. Enviar el text informatiu
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'})
        
        # 2. Enviar totes les imatges com a àlbum
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
    if not os.path.exists(CSV_PATH): return

    rows, headers = [], []
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for r in reader: rows.append(r)

    status_idx = headers.index('Status')
    current_idx, post_data = None, None
    
    for idx, r in enumerate(rows):
        if r[status_idx].strip().lower() == 'pending':
            current_idx = idx
            post_data = dict(zip(headers, r))
            break

    if current_idx is None:
        print("🎉 Tots els posts estan completats!")
        return

    post_id = post_data.get('Post_ID', f"Post_{current_idx + 1}")
    post_type = post_data.get('Type', 'Question')
    print(f"🚀 Generant carrousel ({post_type}) per a {post_id} (MODE PROVA = {TEST_MODE})...")

    # Carregar Fonts
    font_serif_large = ImageFont.truetype(FONT_SERIF_REG_PATH, 58)
    font_serif_med = ImageFont.truetype(FONT_SERIF_REG_PATH, 46)
    font_serif_italic = ImageFont.truetype(FONT_SERIF_ITALIC_PATH, 44)
    font_sans_footer = ImageFont.truetype(FONT_SANS_PATH, 28)

    # Imatge de fons base per a tot el carrousel
    base_bg = generate_hf_background()
    framed_bg = apply_retro_frame_and_overlay(base_bg)

    temp_files = []

    # --- SLIDE 1: PORTADA ---
    s1 = framed_bg.copy()
    d1 = ImageDraw.Draw(s1)
    draw_title_with_underline(d1, post_data.get('Slide_1_Title', ''), post_data.get('Highlight_Word', ''), font_serif_large, 1080, None)
    draw_footer(d1, font_sans_footer, 1080)
    
    f1_path = os.path.join(SLIDES_DIR, f"{post_id}_slide_1.jpg")
    s1.save(f1_path, "JPEG", quality=95)
    temp_files.append(f1_path)

    # --- SLIDES 2 A 6 (SENSE SLIDE 7 CTA) ---
    slide_keys = ['Slide_2_Question_or_Title', 'Slide_3_Question', 'Slide_4_Question', 'Slide_5_Question', 'Slide_6_Question']
    
    for i, key in enumerate(slide_keys):
        s = framed_bg.copy()
        d = ImageDraw.Draw(s)
        
        # Diapositiva tipus TEST (A, B, C, D) a la Slide 2 si és Type = Test
        if i == 0 and post_type.lower() == 'test':
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
                if not opt_text: continue
                d.text((100, y_curr), opt_letter, fill='#FFFFFF', font=font_serif_italic)
                d.text((160, y_curr), opt_text, fill='#FFFFFF', font=font_serif_med)
                y_curr += 65
        else:
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
        
        f_path = os.path.join(SLIDES_DIR, f"{post_id}_slide_{i+2}.jpg")
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
