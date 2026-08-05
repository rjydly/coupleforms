import os
import csv
import random
import requests
import html
import io
import urllib.parse
from PIL import Image, ImageDraw, ImageFont

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'posts.csv')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
SLIDES_DIR = os.path.join(BASE_DIR, 'public_slides')

FONT_BOLD_PATH = os.path.join(BASE_DIR, 'Poppins-Bold.ttf')
FONT_REG_PATH = os.path.join(BASE_DIR, 'Poppins-Regular.ttf')

FONT_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf"
FONT_REG_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf"

# Secrets i variables d'entorn
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "org/repo") # Format: usuari/FormFriends-Couples

def ensure_font(path, url):
    if not os.path.exists(path):
        print(f"📥 Descarregant font des de {url}...")
        res = requests.get(url)
        with open(path, 'wb') as f:
            f.write(res.content)

# ========================================================
# GENERACIÓ D'IMATGES DE FONS RETRO 35MM
# ========================================================
def fetch_retro_background():
    """Genera una imatge estil càmera analògica 35mm sense persones via Pollinations / HuggingFace."""
    prompts = [
        "romantic warm sunset over quiet ocean, vintage 35mm film photography, kodak portra 400 grain, golden hour, cozy mood, no people",
        "aesthetic dimly lit room with candles, analog film 35mm shot, warm tones, retro photography, no people",
        "scenic coastal road during sunset, 35mm disposable camera aesthetic, film grain, nostalgic, no people",
        "view of a soft sunset through a cozy vintage window, 35mm photograph, soft focus, film grain, no people"
    ]
    prompt = random.choice(prompts)
    
    # 1. Intent amb Hugging Face si HF_TOKEN està configurat
    if HF_TOKEN:
        try:
            API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
            headers = {"Authorization": f"Bearer {HF_TOKEN}"}
            res = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=25)
            if res.status_code == 200:
                img = Image.open(io.BytesIO(res.content)).convert('RGB')
                return img.resize((1080, 1080), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"⚠️ HuggingFace error: {e}. Provant fallback...")

    # 2. Fallback gratuït instantani sense Token (Pollinations.ai)
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true&seed={random.randint(1,99999)}"
        res = requests.get(url, timeout=25)
        if res.status_code == 200:
            img = Image.open(io.BytesIO(res.content)).convert('RGB')
            return img.resize((1080, 1080), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"⚠️ Error descarregant fons d'IA: {e}")

    # Fallback de seguretat
    return Image.new('RGB', (1080, 1080), color='#2B1B17')

# ========================================================
# RENDERITZAT DE TEXT I CARROUSEL (PIL)
# ========================================================
def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines

def render_slide(post_data, slide_type, slide_index, bg_base_image):
    # 1. Copiar fons i aplicar capa d'enfosquiment (Dark Overlay)
    bg = bg_base_image.copy()
    overlay = Image.new('RGBA', (1080, 1080), (0, 0, 0, 110))
    bg.paste(overlay, (0, 0), overlay)
    
    canvas = bg.convert('RGBA')
    draw = ImageDraw.Draw(canvas)

    # 2. Dibuixar Contenidor Flotant amb marges laterals i cantonades arrodonides
    margin_x = 70
    margin_y = 110
    container = [margin_x, margin_y, 1080 - margin_x, 1080 - margin_y]
    draw.rounded_rectangle(container, radius=40, fill=(255, 255, 255, 245))

    ensure_font(FONT_BOLD_PATH, FONT_BOLD_URL)
    ensure_font(FONT_REG_PATH, FONT_REG_URL)

    font_title = ImageFont.truetype(FONT_BOLD_PATH, 54)
    font_body = ImageFont.truetype(FONT_BOLD_PATH, 42)
    font_option = ImageFont.truetype(FONT_REG_PATH, 34)
    font_footer = ImageFont.truetype(FONT_REG_PATH, 24)

    # 3. Logo
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert('RGBA')
            logo.thumbnail((140, 50))
            canvas.paste(logo, (margin_x + 50, margin_y + 45), logo)
        except Exception:
            pass

    max_text_width = (1080 - margin_x * 2) - 100

    # ----------------------------------------------------
    # SLIDE 1: PORTADA AMB TEXT SUBRAYAT/RESALTAT
    # ----------------------------------------------------
    if slide_index == 1:
        title = post_data.get('Slide_1_Title', '')
        highlight_word = post_data.get('Highlight_Word', '').lower()

        lines = wrap_text(title, font_title, max_text_width, draw)
        
        line_height = 70
        total_height = len(lines) * line_height
        start_y = (1080 - total_height) // 2 - 20

        current_y = start_y
        for line in lines:
            line_words = line.split()
            line_width = draw.textbbox((0, 0), line, font=font_title)[2]
            start_x = (1080 - line_width) // 2

            x_offset = start_x
            for w in line_words:
                w_clean = w.strip(",.!?").lower()
                w_bbox = draw.textbbox((0, 0), w + " ", font=font_title)
                w_width = w_bbox[2] - w_bbox[0]

                if highlight_word and highlight_word in w_clean:
                    draw.rectangle(
                        [x_offset - 4, current_y + 8, x_offset + w_width - 8, current_y + 62],
                        fill=(255, 223, 128) # Groc pastel suau
                    )

                draw.text((x_offset, current_y), w + " ", font=font_title, fill='#1A1A1A')
                x_offset += w_width

            current_y += line_height

    # ----------------------------------------------------
    # SLIDES POSTERIORS (QUESTIONS O TEST)
    # ----------------------------------------------------
    else:
        post_type = post_data.get('Type', 'Question')

        if post_type == 'Test':
            question = post_data.get('Slide_2_Question_or_Title', '')
            draw.text((1080//2, margin_y + 110), "QUIZ FOR COUPLES", font=font_footer, fill='#888888', anchor='mm')

            lines = wrap_text(question, font_body, max_text_width, draw)
            y_q = margin_y + 180
            for l in lines:
                draw.text((1080//2, y_q), l, font=font_body, fill='#1A1A1A', anchor='mm')
                y_q += 52

            options = [
                post_data.get('Option_A', ''),
                post_data.get('Option_B', ''),
                post_data.get('Option_C', ''),
                post_data.get('Option_D', '')
            ]
            
            box_y = y_q + 30
            for opt in options:
                if not opt: continue
                box_bounds = [margin_x + 40, box_y, 1080 - margin_x - 40, box_y + 65]
                draw.rounded_rectangle(box_bounds, radius=15, fill=(242, 242, 247, 255), outline=(220, 220, 225), width=1)
                draw.text((margin_x + 65, box_y + 16), opt, font=font_option, fill='#2C2C2E')
                box_y += 80

        else: # Type == 'Question'
            q_key = f'Slide_{slide_index}_Question'
            question = post_data.get(q_key, '')
            
            lines = wrap_text(question, font_body, max_text_width, draw)
            total_h = len(lines) * 58
            start_y = (1080 - total_h) // 2

            for l in lines:
                draw.text((1080//2, start_y), l, font=font_body, fill='#111111', anchor='mm')
                start_y += 58

    # CTA Footer permanent
    draw.text((1080//2, 1080 - margin_y - 50), "formfriends.com · link in bio", font=font_footer, fill='#999999', anchor='mm')

    # Guardar a la carpeta pública local del repositori
    os.makedirs(SLIDES_DIR, exist_ok=True)
    filename = f"slide_{slide_index}.jpg"
    output_path = os.path.join(SLIDES_DIR, filename)
    canvas.convert('RGB').save(output_path, 'JPEG', quality=95)
    
    # Construir URL pública directa des del Raw CDN de GitHub
    public_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/public_slides/{filename}"
    return public_url

# ========================================================
# PUBLICACIÓ A BUFFER (GRAPHQL API)
# ========================================================
def post_to_buffer(access_token, image_urls, caption):
    graphql_url = "https://api.bufferapp.com/1/graphql"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    query_profiles = "{ user { account { profiles { id service } } } }"
    r = requests.post(graphql_url, json={"query": query_profiles}, headers=headers)
    
    if r.status_code != 200 or 'data' not in r.json():
        print(f"⚠️ Error obtenint perfils de Buffer: {r.text}")
        return False
        
    profiles = r.json()['data']['user']['account']['profiles']
    profile_ids = [p['id'] for p in profiles if p['service'] in ['instagram', 'tiktok']]

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        post { id }
      }
    }
    """
    
    success = True
    for pid in profile_ids:
        variables = {
            "input": {
                "profileId": pid,
                "text": caption,
                "media": [{"type": "image", "url": u} for u in image_urls]
            }
        }
        res = requests.post(graphql_url, json={"query": mutation, "variables": variables}, headers=headers)
        if res.status_code != 200:
            print(f"❌ Error en enviar post a perfil {pid}: {res.text}")
            success = False
    return success

# ========================================================
# EXECUCIÓ PRINCIPAL
# ========================================================
def main():
    if not os.path.exists(CSV_PATH):
        print("❌ CSV no trobat.")
        return

    rows = []
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for r in reader:
            rows.append(r)

    status_col = headers.index('Status')
    target_row_idx = None
    post_data = {}

    for idx, row in enumerate(rows):
        if row[status_col].strip().lower() == 'pending':
            target_row_idx = idx
            post_data = dict(zip(headers, row))
            break

    if target_row_idx is None:
        print("🎉 Tots els posts estan completats ('Done')!")
        return

    print(f"🚀 Processant {post_data['Post_ID']}: '{post_data['Slide_1_Title']}'...")

    bg_image = fetch_retro_background()

    public_urls = []
    num_slides = 2 if post_data.get('Type') == 'Test' else 6
    
    for i in range(1, num_slides + 1):
        url = render_slide(post_data, post_data.get('Type'), i, bg_image)
        public_urls.append(url)

    caption = f"{post_data['Slide_1_Title']}\n\nTag your partner in the comments below! 👇\n\nFind more couples questions at the link in our bio (formfriends.com) ✨\n\n#couples #relationshipgoals #couplesquiz #deepquestions #formfriends"
    
    if BUFFER_ACCESS_TOKEN:
        print("📤 Enviant el carrousel a Buffer via GitHub Raw CDN...")
        if post_to_buffer(BUFFER_ACCESS_TOKEN, public_urls, caption):
            print("✅ Carrousel enviat a Buffer amb èxit!")
            
            rows[target_row_idx][status_col] = 'Done'
            with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            print("📝 CSV actualitzat a 'Done'.")

if __name__ == "__main__":
    main()
