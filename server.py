from flask import Flask, render_template, request, jsonify, send_from_directory, session
from googletrans import Translator
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime, timedelta
from pathlib import Path
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from flask_session import Session

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['UPLOAD_FOLDER'] = 'downloads'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# Database configuration
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '3306'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'edupath_auth')
}

# Check database connection
def check_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        conn.close()
        return {'status': 'success', 'message': 'Database connected successfully'}
    except mysql.connector.Error as e:
        return {'status': 'error', 'message': f'Database connection failed: {str(e)}'}

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
    return render_template('LandingPage.html', languages=LANGUAGES)

@app.route('/api/navigate/<page>')
def navigate(page):
    valid_pages = ['index', 'login', 'signup', 'forgot', 'chatbot', 'dashboard']
    if page not in valid_pages:
        return jsonify({'message': 'Invalid page'}), 404
    return render_template(f'{page}.html', languages=LANGUAGES)

@app.route('/api/db-status')
def db_status():
    return jsonify(check_db_connection())

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirmPassword')

    if not all([username, email, password, confirm_password]):
        return jsonify({'message': 'All fields are required'}), 400
    if password != confirm_password:
        return jsonify({'message': 'Passwords do not match'}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Check if username already exists
        cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'message': 'Username already exists'}), 400

        # Check if email already exists
        cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'message': 'Email already exists'}), 400

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, password, created_at) VALUES (%s, %s, %s, %s)",
            (username, email, hashed_password, datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Signup successful! Redirecting to login...'}), 200
    except mysql.connector.Error as e:
        return jsonify({'message': f'Database error: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not check_password_hash(user[0], password):
            return jsonify({'message': 'Invalid email or password'}), 401

        session['user'] = email
        return jsonify({'message': 'Login successful'}), 200
    except mysql.connector.Error as e:
        return jsonify({'message': f'Database error: {str(e)}'}), 500

@app.route('/api/forgot', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            return jsonify({'message': 'Email not found'}), 404

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)

        cursor.execute(
            "INSERT INTO password_resets (email, token, expires_at, created_at) VALUES (%s, %s, %s, %s)",
            (email, token, expires_at, datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()

        # For demo purposes, return token (in production, send via email)
        return jsonify({'message': 'Password reset token generated', 'token': token}), 200
    except mysql.connector.Error as e:
        return jsonify({'message': f'Database error: {str(e)}'}), 500

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    token = data.get('token')
    new_password = data.get('newPassword')
    confirm_password = data.get('confirmPassword')

    if not all([email, token, new_password, confirm_password]):
        return jsonify({'message': 'All fields are required'}), 400
    if new_password != confirm_password:
        return jsonify({'message': 'Passwords do not match'}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT token, expires_at FROM password_resets WHERE email = %s ORDER BY created_at DESC LIMIT 1",
            (email,)
        )
        result = cursor.fetchone()

        if not result or result[0] != token:
            cursor.close()
            conn.close()
            return jsonify({'message': 'Invalid or expired token'}), 400

        token_expiry = result[1]
        if datetime.now() > token_expiry:
            cursor.close()
            conn.close()
            return jsonify({'message': 'Token has expired'}), 400

        hashed_password = generate_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password = %s WHERE email = %s",
            (hashed_password, email)
        )
        cursor.execute("DELETE FROM password_resets WHERE email = %s", (email,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Password reset successfully'}), 200
    except mysql.connector.Error as e:
        return jsonify({'message': f'Database error: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'message': 'Logged out successfully'}), 200

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