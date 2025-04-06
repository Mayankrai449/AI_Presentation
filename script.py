import requests
import json
import uuid
import websocket
import base64
import random
import ssl
import argparse
import logging
from datetime import datetime
import os
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup
from PIL import Image
import io
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('presentation_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

AUTH_TOKEN = None
BASE_API_URL = "https://alai-standalone-backend.getalai.com"
AUTH_URL = "https://api.getalai.com/auth/v1/token?grant_type=password"
PRESENTATION_ID = None
SLIDE_ID = None
API_KEY = os.getenv('ALAI_API_KEY')
FIRE_CRAWL_API_KEY = os.getenv('FIRE_CRAWL_API_KEY')
SLIDES_DATA = []
ALL_RESPONSES = []

def configure_argparse():
    """Configure and parse command line arguments"""
    parser = argparse.ArgumentParser(description='Generate Alai presentation from webpage content')
    parser.add_argument('url', help='URL of the webpage to scrape')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    return parser.parse_args()

def scrape_webpage(target_url, api_token):
    """Scrape webpage content using Firecrawl API"""
    firecrawl_url = "https://api.firecrawl.dev/v1/scrape"

    os.makedirs("scraped_data", exist_ok=True)
    os.makedirs("scraped_data/images", exist_ok=True)

    payload = {
        "url": target_url,
        "formats": ["markdown", "html"],
        "onlyMainContent": True,
        "removeBase64Images": False,
        "blockAds": True
    }

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    def save_image(image_data, extension, index):
        """Helper function to save image with proper format validation"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            if extension.lower() in ['.jpg', '.jpeg']:
                format = 'JPEG'
                ext = '.jpg'
            elif extension.lower() == '.png':
                format = 'PNG'
                ext = '.png'
            elif extension.lower() == '.gif':
                format = 'GIF'
                ext = '.gif'
            elif extension.lower() == '.webp':
                format = 'WEBP'
                ext = '.webp'
            else:
                format = 'JPEG'
                ext = '.jpg'
            
            img_filename = f"scraped_data/images/img{index}{ext}"
            img.save(img_filename, format=format)
            logger.info(f"Saved image to {img_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process image: {str(e)}")
            return False

    try:
        if not api_token or api_token == "your_api_token_here":
            raise ValueError("Please provide a valid API token")
        if not target_url.startswith("http"):
            raise ValueError("URL must start with http:// or https://")

        logger.info(f"Scraping webpage: {target_url}")
        response = requests.post(firecrawl_url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

        clean_text = ""
        if "data" in result and "markdown" in result["data"]:
            markdown_content = result["data"]["markdown"]

            clean_text = markdown_content
            clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text)
            clean_text = re.sub(r'\[([^\]]+)\]\((.*?)\)', r'\1', clean_text)
            clean_text = re.sub(r'http[s]?://\S+', '', clean_text)
            clean_text = re.sub(r'^#+\s+', '', clean_text, flags=re.MULTILINE)
            clean_text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', clean_text)
            clean_text = re.sub(r'(\*|_)(.*?)\1', r'\2', clean_text)
            clean_text = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', clean_text)
            clean_text = re.sub(r'\|.*\|', '', clean_text)
            clean_text = re.sub(r'^\s*[-*+]\s+', '', clean_text, flags=re.MULTILINE)
            clean_text = re.sub(r'^-{3,}|_{3,}|\*{3,}', '', clean_text, flags=re.MULTILINE)
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
            clean_text = re.sub(r'[ \t]+', ' ', clean_text)
            clean_text = clean_text.strip()

            safe_filename = target_url.replace('https://', '').replace('http://', '').replace('/', '_')
            text_filename = f"scraped_data/{safe_filename}.txt"
            
            with open(text_filename, 'w', encoding='utf-8') as f:
                f.write(clean_text)

            logger.info(f"Saved clean text to {text_filename}")
        else:
            logger.warning("No markdown content found in the scraped result.")

        if "data" in result and "html" in result["data"]:
            html_content = result["data"]["html"]
            soup = BeautifulSoup(html_content, 'html.parser')
            
            img_tags = soup.find_all('img', src=True)
            downloaded = 0
            
            for i, img in enumerate(img_tags):
                if downloaded >= 10:
                    break
                
                img_src = img['src']
                
                if img_src.startswith('data:image'):
                    try:
                        img_format = img_src.split(';')[0].split('/')[1]
                        img_data = img_src.split(',')[1]
                        
                        ext_map = {
                            'jpeg': '.jpg',
                            'jpg': '.jpg',
                            'png': '.png',
                            'gif': '.gif',
                            'webp': '.webp'
                        }
                        ext = ext_map.get(img_format.lower(), '.jpg')
                        
                        decoded_img = base64.b64decode(img_data)
                        
                        if save_image(decoded_img, ext, downloaded+1):
                            downloaded += 1
                            
                    except Exception as e:
                        logger.error(f"Failed to save base64 image: {str(e)}")
                else:
                    try:
                        img_url = urljoin(target_url, img_src)
                        img_ext = os.path.splitext(img_url.split('?')[0])[1].lower()
                        if not img_ext or img_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                            img_ext = '.jpg'
                        
                        img_response = requests.get(img_url, timeout=10)
                        img_response.raise_for_status()
                        
                        if save_image(img_response.content, img_ext, downloaded+1):
                            downloaded += 1
                            
                    except Exception as e:
                        logger.error(f"Failed to download image {img_src}: {str(e)}")
        
        if not img_tags or downloaded == 0:
            logger.warning("No images found in the scraped result.")
            with open("scraped_data/images/.no_images_found", 'w') as f:
                f.write(f"No images found for {target_url}")

        return clean_text

    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return error_msg
    
def save_responses_to_file():
    """Save all collected responses to a JSON file with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"presentation_responses_{timestamp}.json"
    
    response_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "presentation_id": PRESENTATION_ID,
            "slide_id": SLIDE_ID
        },
        "responses": ALL_RESPONSES
    }
    
    with open(filename, 'w') as f:
        json.dump(response_data, f, indent=4)
    
    logger.info(f"All responses saved to {filename}")
    return filename

def add_response(step_name, response_data, success=True, error=None):
    """Add a response to the global collection with metadata"""
    response_entry = {
        "timestamp": datetime.now().isoformat(),
        "step": step_name,
        "success": success,
        "data": response_data
    }
    
    if error:
        response_entry["error"] = str(error)
    
    ALL_RESPONSES.append(response_entry)
    return response_entry

def authenticate():
    """Authenticate to Alai API and get access token"""
    global AUTH_TOKEN
    
    logger.info("Authenticating to Alai API")
    
    headers = {
        "ApiKey": f"{API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "email": os.getenv('ALAI_EMAIL'),
        "password": os.getenv('ALAI_PASSWORD'),
        "gotrue_meta_security": {}
    }
    
    try:
        response = requests.post(AUTH_URL, headers=headers, json=data)
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            AUTH_TOKEN = response_data.get("access_token")
            logger.info("Authentication successful")
            add_response("authentication", response_data)
            return True
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Authentication failed: {error_msg}")
            add_response("authentication", response_data, False, error_msg)
            return False
            
    except Exception as e:
        error_msg = f"Exception during authentication: {str(e)}"
        logger.error(error_msg)
        add_response("authentication", None, False, error_msg)
        return False

def get_existing_presentations():
    """Get list of existing presentations to avoid ID collision"""
    logger.info("Getting existing presentations list")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    
    try:
        response = requests.get(f"{BASE_API_URL}/get-presentations-list", headers=headers)
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            existing_ids = [p["id"] for p in response_data]
            logger.info(f"Retrieved {len(existing_ids)} existing presentations")
            add_response("get_existing_presentations", response_data)
            return existing_ids
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to get presentations: {error_msg}")
            add_response("get_existing_presentations", response_data, False, error_msg)
            return []
            
    except Exception as e:
        error_msg = f"Exception getting presentations: {str(e)}"
        logger.error(error_msg)
        add_response("get_existing_presentations", None, False, error_msg)
        return []

def generate_unique_id(existing_ids):
    """Generate a unique presentation ID that doesn't collide with existing ones"""
    while True:
        new_id = str(uuid.uuid4())
        if new_id not in existing_ids:
            return new_id

def create_new_presentation(content_data):
    """Create a new presentation with generated ID"""
    global PRESENTATION_ID
    
    PRESENTATION_ID = generate_unique_id(get_existing_presentations())
    add_response("presentation_id", PRESENTATION_ID)
    
    logger.info("Creating new presentation")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    
    data = {
        "presentation_id": PRESENTATION_ID,
        "presentation_title": "Untiled Presentation",
        "create_first_slide": True,
        "theme_id": "a6bff6e5-3afc-4336-830b-fbc710081012",
        "default_color_set_id": 0
    }
    
    try:
        response = requests.post(f"{BASE_API_URL}/create-new-presentation", headers=headers, json=data)
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            logger.info(f"Created new presentation with ID: {PRESENTATION_ID}")
            add_response("create_new_presentation", response_data)
            return response_data
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to create presentation: {error_msg}")
            add_response("create_new_presentation", response_data, False, error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Exception creating presentation: {str(e)}"
        logger.error(error_msg)
        add_response("create_new_presentation", None, False, error_msg)
        return None

def get_presentation_details():
    """Get details of the created presentation to extract slide ID"""
    global SLIDE_ID
    
    logger.info("Getting presentation details")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    
    try:
        response = requests.get(f"{BASE_API_URL}/get-presentation/{PRESENTATION_ID}", headers=headers)
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            if response_data.get("slides") and len(response_data["slides"]) > 0:
                SLIDE_ID = response_data["slides"][0]["id"]
                logger.info(f"Retrieved presentation details. Slide ID: {SLIDE_ID}")
                add_response("get_presentation_details", response_data)
                return response_data
            else:
                error_msg = "No slides found in the presentation"
                logger.error(error_msg)
                add_response("get_presentation_details", response_data, False, error_msg)
                return None
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to get presentation details: {error_msg}")
            add_response("get_presentation_details", response_data, False, error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Exception getting presentation details: {str(e)}"
        logger.error(error_msg)
        add_response("get_presentation_details", None, False, error_msg)
        return None

def get_presentation_questions():
    """Get questions for the presentation"""
    logger.info("Getting presentation questions")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }
    
    try:
        response = requests.get(f"{BASE_API_URL}/get-presentation-questions/{PRESENTATION_ID}", headers=headers)
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            logger.info("Retrieved presentation questions")
            add_response("get_presentation_questions", response_data)
            return response_data
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to get presentation questions: {error_msg}")
            add_response("get_presentation_questions", response_data, False, error_msg)
            return []
            
    except Exception as e:
        error_msg = f"Exception getting presentation questions: {str(e)}"
        logger.error(error_msg)
        add_response("get_presentation_questions", None, False, error_msg)
        return []

def get_websocket_headers():
    """Generate WebSocket headers with proper Sec-WebSocket-Key"""
    key = base64.b64encode(bytes([random.randint(0, 255) for _ in range(16)])).decode('utf-8')
    return []

class CustomWebSocket(websocket.WebSocketApp):
    def _get_custom_headers(self):
        return get_websocket_headers()

def generate_slides_outline(content_data, instructions):
    """Generate slide outlines using WebSocket connection"""
    global SLIDES_DATA
    
    presentation_questions = get_presentation_questions()
    presentation_questions[0]["answer"] = "Professional Meeting"
    presentation_questions[1]["answer"] = "Business Executives who need detailed information"
    presentation_questions[2]["answer"] = "medium to Vast"

    message = {
        "auth_token": AUTH_TOKEN,
        "presentation_id": PRESENTATION_ID,
        "slide_order": 0,
        "raw_context": content_data,
        "presentation_instructions": instructions+"Keep images null for all slides",
        "slide_range": "2-5",
        "presentation_questions": presentation_questions
    }
    
    add_response("generate_slides_outline_request", message)
    
    response_received = False
    ssl_options = {"cert_reqs": ssl.CERT_NONE}
    
    def on_open(ws):
        ws.send(json.dumps(message))
    
    def on_message(ws, msg):
        nonlocal response_received
        try:
            response_data = json.loads(msg)
            logger.debug(f"Received slide outline response: {response_data}")
            
            add_response("generate_slides_outline_response", response_data)
            SLIDES_DATA.append(response_data)
            response_received = True
        except json.JSONDecodeError as e:
            add_response("generate_slides_outline_response", None, False, str(e))
    
    def on_error(ws, error):
        add_response("generate_slides_outline_error", None, False, str(error))
    
    logger.info("Generating slides outline via WebSocket")
    ws = CustomWebSocket(
        "wss://alai-standalone-backend.getalai.com/ws/generate-slides-outline",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error
    )
    
    ws.run_forever(sslopt=ssl_options)
    return SLIDES_DATA if response_received else None

def get_calibration_sample_text(content_data):
    """Get calibration sample text"""
    logger.info("Getting calibration sample text")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "presentation_id": PRESENTATION_ID,
        "raw_context": content_data
    }
    
    try:
        response = requests.post(f"{BASE_API_URL}/get-calibration-sample-text", headers=headers, json=data)
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            add_response("get_calibration_sample_text", response_data)
            return response_data
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            add_response("get_calibration_sample_text", response_data, False, error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Exception getting calibration sample: {str(e)}"
        add_response("get_calibration_sample_text", None, False, error_msg)
        return None

def create_slides_from_outlines(content_data, instructions):
    """Create actual slides from outlines using WebSocket connection"""
    message = {
        "auth_token": AUTH_TOKEN,
        "presentation_id": PRESENTATION_ID,
        "slide_id": SLIDE_ID,
        "slide_outlines": SLIDES_DATA,
        "raw_context": content_data,
        "presentation_instructions": instructions,
        "starting_slide_order": 0,
        "update_tone_verbosity_calibration_status": True
    }
    
    add_response("create_slides_from_outlines_request", message)
    
    response_messages = []
    ssl_options = {"cert_reqs": ssl.CERT_NONE}
    
    def on_open(ws):
        ws.send(json.dumps(message))
    
    def on_message(ws, msg):
        try:
            response_data = json.loads(msg)
            response_messages.append(response_data)
            add_response("create_slides_from_outlines_response", response_data)
        except json.JSONDecodeError as e:
            add_response("create_slides_from_outlines_response", None, False, str(e))
    
    def on_error(ws, error):
        add_response("create_slides_from_outlines_error", None, False, str(error))
    
    logger.info("Creating slides from outlines via WebSocket")
    ws = CustomWebSocket(
        "wss://alai-standalone-backend.getalai.com/ws/create-slides-from-outlines",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error
    )
    
    ws.run_forever(sslopt=ssl_options)
    return response_messages if response_messages else None

def generate_shareable_link():
    """Generate a shareable link for the presentation"""
    logger.info("Generating shareable link")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "presentation_id": PRESENTATION_ID
    }
    
    try:
        response = requests.post(
            f"{BASE_API_URL}/upsert-presentation-share",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            share_code = response.text.strip('"')
            shareable_link = f"https://app.getalai.com/view/{share_code}"
            logger.info(f"Generated shareable link: {shareable_link}")
            add_response("generate_shareable_link", {
                "share_code": share_code,
                "shareable_link": shareable_link
            })
            return shareable_link
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to generate shareable link: {error_msg}")
            add_response("generate_shareable_link", None, False, error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Exception generating shareable link: {str(e)}"
        logger.error(error_msg)
        add_response("generate_shareable_link", None, False, error_msg)
        return None

def upload_images_to_presentation(image_paths):
    logger.info("Uploading images to presentation")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
    }

    valid_images = []
    for path in image_paths:
        if not os.path.isfile(path):
            logger.warning(f"File not found: {path}")
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.jpg', '.jpeg'):
            valid_images.append(path)
        else:
            logger.warning(f"Skipping non-JPG file: {path}")
    
    valid_images = valid_images[:5]
    if not valid_images:
        logger.warning("No valid JPG images to upload")
        return None

    files = []
    data = {
        'upload_input': json.dumps({
            'presentation_id': PRESENTATION_ID
        })
    }

    for path in valid_images:
        file = open(path, 'rb')
        filename = os.path.basename(path)
        files.append(('files', (filename, file, 'image/jpeg')))
    
    logger.debug(f"Preparing to upload {len(files)} images")
    try:
        response = requests.post(
            f"{BASE_API_URL}/upload-images-for-slide-generation",
            headers=headers,
            data=data,
            files=files
        )
        response_data = response.json() if response.content else {}

        if response.status_code == 200:
            logger.info("Successfully uploaded images")
            add_response("upload_images_to_presentation", response_data)
            return response_data
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to upload images: {error_msg}")
            add_response("upload_images_to_presentation", response_data, False, error_msg)
            return None

    except Exception as e:
        error_msg = f"Exception uploading images: {str(e)}"
        logger.error(error_msg)
        add_response("upload_images_to_presentation", None, False, error_msg)
        return None

    finally:
        for _, file_tuple in files:
            if len(file_tuple) > 1 and hasattr(file_tuple[1], 'close'):
                file_tuple[1].close()

def add_images_to_existing_slides(images_data, slides_data):
    """Add images to existing slides starting from first slide"""
    if not images_data or not slides_data:
        return slides_data
    
    try:
        image_list = images_data.get("images", [])
        if not image_list:
            return slides_data
        
        if not isinstance(slides_data, list):
            logger.error("Invalid slides_data format - expected list")
            return slides_data
            
        for i, image in enumerate(image_list[:5]):
            if i >= len(slides_data):
                logger.warning(f"No more slides to add images to (tried to add to slide {i})")
                break
                
            current_slide = slides_data[i]
            
            if "images_on_slide" not in current_slide or current_slide["images_on_slide"] is None:
                current_slide["images_on_slide"] = []
            
            current_slide["images_on_slide"].append(image)

        return slides_data
        
    except Exception as e:
        logger.error(f"Error adding images to slides: {str(e)}")
        return slides_data

def create_and_stream_slide_variants(slide_data):
    """Create and stream slide variants using WebSocket connection"""
    logger.info(f"Creating and streaming slide variants for slide {slide_data['id']}")
    
    images_on_slide = slide_data["slide_outline"].get("images_on_slide", [])
    logger.debug(f"Images on slide: {images_on_slide}")
    
    message = {
        "auth_token": AUTH_TOKEN,
        "presentation_id": PRESENTATION_ID,
        "slide_id": slide_data["id"],
        "slide_specific_context": slide_data["slide_outline"]["slide_context"],
        "images_on_slide": images_on_slide,
        "additional_instructions": slide_data["slide_outline"]["slide_instructions"],
        "layout_type": "AI_GENERATED_LAYOUT",
        "update_tone_verbosity_calibration_status": False
    }

    logger.debug(f"Message payload: {json.dumps(message, indent=4)}")
    add_response("create_and_stream_slide_variants_request", message)

    response_messages = []
    ssl_options = {"cert_reqs": ssl.CERT_NONE}

    def on_open(ws):
        try:
            logger.debug(f"Sending message to create slide variants for slide {slide_data['id']}")
            ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error in on_open: {str(e)}")
            add_response("create_and_stream_slide_variants_error", None, False, f"on_open error: {str(e)}")

    def on_message(ws, msg):
        try:
            logger.debug(f"Received message: {msg}")
            response_data = json.loads(msg)
            response_messages.append(response_data)
            add_response("create_and_stream_slide_variants_response", response_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {str(e)}")
            add_response("create_and_stream_slide_variants_response", None, False, f"JSON Decode Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error in on_message: {str(e)}")
            add_response("create_and_stream_slide_variants_response", None, False, f"Error in on_message: {str(e)}")

    def on_error(ws, error):
        logger.error(f"WebSocket error: {str(error)}")
        add_response("create_and_stream_slide_variants_error", None, False, f"WebSocket error: {str(error)}")

    try:
        ws = CustomWebSocket(
            "wss://alai-standalone-backend.getalai.com/ws/create-and-stream-slide-variants",
            on_open=on_open,
            on_message=on_message,
            on_error=on_error
        )
        ws.run_forever(sslopt=ssl_options)
    except Exception as e:
        logger.error(f"WebSocket connection failed: {str(e)}")
        add_response("create_and_stream_slide_variants_error", None, False, f"WebSocket connection failed: {str(e)}")

    if response_messages:
        logger.debug(f"Received {len(response_messages)} response messages")
        return response_messages
    else:
        logger.warning("No response messages received.")
        return None

def set_active_variant(slide_id, variant_id):
    """Set the active variant for a slide"""
    logger.info(f"Setting active variant for slide {slide_id}")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "slide_id": slide_id,
        "variant_id": variant_id
    }
    
    try:
        response = requests.post(
            f"{BASE_API_URL}/set-active-variant",
            headers=headers,
            json=data
        )
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            logger.info(f"Set active variant {variant_id} for slide {slide_id}")
            add_response("set_active_variant", response_data)
            return response_data
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to set active variant: {error_msg}")
            add_response("set_active_variant", response_data, False, error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Exception setting active variant: {str(e)}"
        logger.error(error_msg)
        add_response("set_active_variant", None, False, error_msg)
        return None

def update_slide_entity(slide_data, variant_id):
    """Update slide entity with active variant ID"""
    logger.info(f"Updating slide entity for slide {slide_data['id']}")
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    slide_data["active_variant_id"] = variant_id
    
    try:
        response = requests.post(
            f"{BASE_API_URL}/update-slide-entity",
            headers=headers,
            json=slide_data
        )
        response_data = response.json() if response.content else {}
        
        if response.status_code == 200:
            logger.info(f"Updated slide entity for slide {slide_data['id']}")
            add_response("update_slide_entity", response_data)
            return response_data
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            logger.error(f"Failed to update slide entity: {error_msg}")
            add_response("update_slide_entity", response_data, False, error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Exception updating slide entity: {str(e)}"
        logger.error(error_msg)
        add_response("update_slide_entity", None, False, error_msg)
        return None

def process_slide_variants(slides_data):
    """Process each slide to create variants, set active variant, and update slide entity"""
    if not slides_data or "slides" not in slides_data[0]:
        logger.error("No slides data found to process variants")
        return False
    
    presentation_slides = slides_data[0]["slides"]
    sorted_slides = sorted(presentation_slides, key=lambda x: x["slide_order"])
    
    for slide in sorted_slides:
        logger.info(f"Processing slide {slide['slide_order']}: {slide['slide_outline']['slide_title']}")
        
        variant_responses = create_and_stream_slide_variants(slide)
        if not variant_responses or len(variant_responses) < 2:
            logger.error(f"Failed to get variant responses for slide {slide['id']}")
            continue
        
        slide_entity_data = variant_responses[0]
        
        if len(variant_responses) >= 2 and "id" in variant_responses[1]:
            variant_id = variant_responses[1]["id"]
            
            set_active_variant_result = set_active_variant(slide["id"], variant_id)
            if not set_active_variant_result:
                continue
            
            update_slide_entity(slide_entity_data, variant_id)
        else:
            logger.error(f"No variant ID found in responses for slide {slide['id']}")
    
    return True


def generate_presentation(content_data, instructions="", image_paths=None):
    """Main function to orchestrate the entire presentation generation process"""

    add_response("start", {
        "content_data": content_data[:200] + "..." if len(content_data) > 200 else content_data,
        "instructions": instructions,
        "image_paths": image_paths if image_paths else []
    })
    
    try:
        if not authenticate():
            return False
        
        presentation_data = create_new_presentation(content_data)
        if not presentation_data:
            return False
        
        presentation_details = get_presentation_details()
        if not presentation_details:
            return False
        
        slides_data = generate_slides_outline(content_data, instructions)
        if not slides_data:
            return False
        
        if image_paths:
            logger.info(f"Attempting to upload {len(image_paths)} images")
            images_data = upload_images_to_presentation(image_paths)
            if images_data:
                logger.info("Adding images to slides")
                slides_data = add_images_to_existing_slides(images_data, slides_data)
            else:
                logger.warning("Image upload failed or no images returned")
        
        calibration_data = get_calibration_sample_text(content_data)
        if not calibration_data:
            logger.warning("Failed to get calibration sample text")
        
        logger.info("Creating slides from outlines")
        slides_creation_responses = create_slides_from_outlines(content_data, instructions)
        if not slides_creation_responses:
            logger.error("Failed to create slides from outlines")
            return False
        
        logger.info("Processing slide variants")
        if not process_slide_variants(slides_creation_responses):
            logger.warning("Some slide variants may not have processed correctly")
        
        logger.info("Generating shareable link")
        shareable_link = generate_shareable_link()
        if not shareable_link:
            shareable_link = f"https://app.getalai.com/view/{PRESENTATION_ID}"
            logger.warning(f"Using fallback shareable link: {shareable_link}")
        
        logger.info("Presentation generation complete")
        save_responses_to_file()
        return shareable_link
        
    except Exception as e:
        logger.error(f"Error in generate_presentation: {str(e)}")
        add_response("error", None, False, str(e))
        save_responses_to_file()
        return False

if __name__ == "__main__":
    args = configure_argparse()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        websocket.enableTrace(True)
    
    content = scrape_webpage(args.url, FIRE_CRAWL_API_KEY)
    
    instructions = """Create a professional presentation with exactly 5 slides, designed for a business audience. 
    Structure the content as follows: Slide 1 is an engaging title slide with a concise subtitle summarizing the topic; 
    Slides 2-4 are content slides with key points derived from the provided data; 
    Slide 5 is a conclusion slide with actionable insights or a summary. 
    Use bullet points or tables for clarity, ensuring visually appealing formats with consistent fonts and spacing. 
    Maintain a professional and concise tone throughout, avoiding jargon unless contextually appropriate. 
    Incorporate provided images as follows: include one relevant image per slide (Slides 1, 2, 3, 4, and 5), 
    each sized to approximately 1/4th of the slide area, positioned to complement the text (e.g., right-aligned or top-aligned). 
    If fewer than 5 images are provided, prioritize their placement on content slides (2-4) and use subtle placeholders or icons on remaining slides. 
    Apply a cohesive color scheme (e.g., corporate blues or neutrals) and minimal animations to enhance professionalism. 
    Ensure each slide is complete, self-contained, and balanced in content and design."""

    image_dir = "scraped_data/images"
    image_paths = [os.path.join(image_dir, filename) for filename in os.listdir(image_dir) 
              if os.path.isfile(os.path.join(image_dir, filename)) 
              and filename.lower().endswith(('.jpg', '.jpeg'))]
    logger.debug(f"Found image paths: {image_paths}")
    
    shareable_link = generate_presentation(content, instructions, image_paths)
    if shareable_link:
        logger.info(f"\nPresentation available at: {shareable_link}")
    else:
        logger.error("\nFailed to create presentation")