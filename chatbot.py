from flask import Flask, render_template, request, jsonify, send_from_directory
from googletrans import Translator
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
from pathlib import Path

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['UPLOAD_FOLDER'] = 'downloads'
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# Configure Google Gemini AI
genai.configure(api_key=os.getenv('GOOGLE_API_KEY', 'YOUR_GOOGLE_API_KEY'))
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction="""
    You are an expert social media content assistant. Your task is to generate engaging social media posts or answer user queries about social media automation. Provide:

    - **Caption**: A short, engaging caption optimized for the specified platform(s) if requested.
    - **Video Script (if applicable)**: A brief description of a video concept.
    - **Tone and Style**: Match the requested tone (e.g., professional, casual, humorous).
    - **Platform Optimization**: Tailor content to platforms like TikTok, LinkedIn, etc.

    For general queries, provide clear, concise, and helpful responses. Format the response clearly with bold headers if generating content.
    """,
    generation_config={
        'temperature': 0.7,
        'top_p': 0.9,
        'top_k': 40,
        'max_output_tokens': 1000,
    }
)

# Initialize translator
translator = Translator()

# Supported languages
LANGUAGES = {
    'en': {'name': 'English', 'flag': '🇬🇧'},
    'es': {'name': 'Spanish', 'flag': '🇪🇸'},
    'fr': {'name': 'French', 'flag': '🇫🇷'},
    'de': {'name': 'German', 'flag': '🇩🇪'},
    'it': {'name': 'Italian', 'flag': '🇮🇹'},
    'pt': {'name': 'Portuguese', 'flag': '🇵🇹'},
    'ru': {'name': 'Russian', 'flag': '🇷🇺'},
    'zh': {'name': 'Chinese', 'flag': '🇨🇳'},
    'ja': {'name': 'Japanese', 'flag': '🇯🇵'},
    'ar': {'name': 'Arabic', 'flag': '🇸🇦'},
    'hi': {'name': 'Hindi', 'flag': '🇮🇳'},
}

def translate_text(text, dest_lang='en'):
    try:
        if dest_lang == 'en':
            return text
        translation = translator.translate(text, dest=dest_lang)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

# Routes
@app.route('/')
def index():
    return render_template('landingpage.html', languages=LANGUAGES)

@app.route('/chatpage')
def chat_page():
    return render_template('chatbot.html', languages=LANGUAGES)

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    user_input = data.get('query', '').strip()
    input_lang = data.get('input_lang', 'en')
    output_lang = data.get('output_lang', 'en')

    if not user_input:
        return jsonify({'response': '⚠️ Please enter a message.', 'lang': output_lang})

    try:
        if input_lang != 'en':
            user_input = translate_text(user_input, 'en')

        response = model.generate_content(user_input)
        text = response.text.strip() if response.text else '⚠️ No response received from the model.'

        if output_lang != 'en':
            text = translate_text(text, output_lang)

        return jsonify({'response': text, 'lang': output_lang})
    except Exception as e:
        error_msg = f'❌ Error: {str(e)}'
        if output_lang != 'en':
            error_msg = translate_text(error_msg, output_lang)
        return jsonify({'response': error_msg, 'lang': output_lang})

@app.route('/download', methods=['POST'])
def download_text():
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({'status': 'error', 'message': 'No text to download'}), 400
    
    filename = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        return jsonify({'status': 'success', 'url': f'/downloads/{filename}'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/downloads/<filename>')
def download_file():
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)