import whisper
from moviepy.editor import VideoFileClip
import os

# Load Whisper model
model = whisper.load_model("base")

def extract_audio_with_moviepy(video_path):
    audio_path = video_path.replace(".mp4", ".wav")
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path)
    return audio_path

# Full file path to your video
file_path = r"D:\UK Project  post Automation\AI-Automation-social-media-posting\My recording 3.mp4"

# Convert video to wav
wav_path = extract_audio_with_moviepy(file_path)

# Transcribe
result = model.transcribe(wav_path)
print("\n🎙️ Transcription:")
print(result["text"])
