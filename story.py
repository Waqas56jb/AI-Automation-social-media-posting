import os
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import whisper
from dotenv import load_dotenv
import logging
import tempfile
import ffmpeg

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# Load Whisper model
whisper_model = whisper.load_model("base")

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'audio')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB limit for longer recordings

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        audio_file = request.files['file']
        filename = secure_filename(audio_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(file_path)

        # Convert video to audio if necessary
        if audio_file.content_type.startswith('video/'):
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_audio.wav')
            try:
                ffmpeg.input(file_path).output(audio_path, format='wav', acodec='pcm_s16le', ac=1, ar='16000').run(overwrite_output=True)
                file_path = audio_path
            except ffmpeg.Error as e:
                os.remove(file_path)
                return jsonify({'error': f'Video conversion failed: {str(e)}'}), 500

        # Transcribe using Whisper
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_file.write(open(file_path, 'rb').read())
            temp_file_path = temp_file.name
        result = whisper_model.transcribe(temp_file_path)
        transcribed_text = result['text'].strip()

        # Clean up temporary files
        os.remove(file_path)
        if 'audio_path' in locals():
            os.remove(audio_path)
        os.remove(temp_file_path)

        return jsonify({'transcript': transcribed_text})

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/submit_text', methods=['POST'])
def submit_text():
    try:
        data = request.json
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'No text provided'}), 400

        logger.info(f"Submitted text: {text}")
        return jsonify({'message': 'Text submitted successfully!'})

    except Exception as e:
        logger.error(f"Submission error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_story', methods=['POST'])
def generate_story():
    try:
        data = request.json
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'No text provided for story generation'}), 400

        # Fix grammar, spelling, and context
        prompt = f"Correct the grammar, spelling, and context of the following text, then create a lengthy, detailed story based on it: {text}. The story should be at least 500 words, rich in description, and include a beginning, middle, and end. Include the current date and time: 04:42 AM PKT, Thursday, June 26, 2025, as part of the setting."
        response = gemini_model.generate_content(prompt)
        story = response.text.strip()

        return jsonify({'story': story})

    except Exception as e:
        logger.error(f"Story generation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)