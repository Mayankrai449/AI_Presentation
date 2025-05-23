# Webpage to AI Presentation Generator

This project is an initiative to create a tool that converts any webpage URL into a shareable presentation link using Alai's platform. The tool leverages the Firecrawl API to scrape webpage content and processes it through Alai's undocumented API (reverse-engineered via Chrome's network tab) to generate a professional 5-slide presentation. To optimize the output, I designed a structured slide schema, comprising a title slide with a concise headline, content slides with hierarchically organized text extracted from the webpage, and a conclusion slide summarizing key points, all styled with a professional business tone. Additionally, I implemented an image extraction and resizing pipeline, selecting one relevant image per slide from the webpage, and embedding it to enhance visual coherence and presentation polish.

![pptx](images/ppt2.png) 

![pptx](images/ppt1.png)

## Setup

### 1. Clone the Repository

Clone this repository to your local machine:
```bash
git clone https://github.com/Mayankrai449/ALAI_Presentation-backend-.git
cd ALAI_Presentation-backend-
```

### 2. Install Dependencies

Install the required Python packages listed in requirements.txt:
```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root and add the following variables with your credentials:
```text
FIRE_CRAWL_API_KEY=your_fire_crawl_api_key_here
ALAI_API_KEY=your_alai_api_key_here
ALAI_EMAIL=your_alai_email_here
ALAI_PASSWORD=your_alai_password_here
```
Refer .env.example for a template. Make sure to replace the placeholders with your actual API keys and credentials.

- **FIRE_CRAWL_API_KEY**: Get this by signing up at Firecrawl.
- **ALAI_API_KEY, ALAI_EMAIL, ALAI_PASSWORD**: Obtain these by creating an account at getalai.com.

## Running the Script

Run the script from the terminal, providing a URL as an argument:
Example:
```bash
python3 script.py https://en.wikipedia.org/wiki/Cat
```

Replace `https://en.wikipedia.org/wiki/Cat` with any webpage URL you want to convert into a presentation.

The script will output a shareable link (e.g., `https://app.getalai.com/view/[share-code]`) if successful.
Example: `https://app.getalai.com/view/4bNmEBCOSsmzWnxgULdh8w`

## Directory Creation

While scraping data, the script creates a scraped_data directory with two subcomponents:
- `scraped_data/`: Stores the cleaned text content from the webpage as a .txt file.
- `scraped_data/images/`: Saves up to 10 images extracted from the webpage (e.g., .jpg, .png).

## Overall Working

1. **Scraping**: The script uses the Firecrawl API to scrape markdown text and images from the input URL, saving them in scraped_data/.
2. **Authentication**: It authenticates with Alai's API using a token (stored in AUTH_TOKEN), which expires every 30 minutes to 2 hours.
3. **Presentation Creation**: It creates a new Alai presentation with a unique ID, then generates 5 slides using WebSocket endpoints:
   - Create new presentation with unique id.
   - Get presentation and its questions.
   - Generate slide outlines using websockets.
4. **Image Integration**: Up to 5 scraped images are uploaded and added to slides, sized at ~1/4th of the slide area.
5. **Output**: A shareable link is generated and logged, with all API responses saved in a JSON file for debugging.


## Requirements

See `requirements.txt` for the full list of dependencies, including requests, websocket-client, beautifulsoup4, Pillow, and python-dotenv.

## Notes

- Ensure your API keys are valid and the `.env` file is correctly configured.
- The script logs progress to `presentation_generator.log` and saves responses in a timestamped JSON file (e.g., `presentation_responses_YYYYMMDD_HHMMSS.json`).
