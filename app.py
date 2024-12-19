from flask import Flask, request, jsonify, render_template,send_from_directory
from flask_cors import CORS
from google.oauth2 import service_account
from google.cloud import speech
import ffmpeg
from pydub import AudioSegment
from pydub.utils import make_chunks
from tempfile import NamedTemporaryFile
import os

app = Flask(__name__, static_folder='build', static_url_path='')
CORS(app)

client_file = 'sa_speech_demo.json'
credentials = service_account.Credentials.from_service_account_file(client_file)
speech_client = speech.SpeechClient(credentials=credentials)
print(credentials.service_account_email)  # To print the email associated with the credentials

print(speech_client)
# Existing route
@app.route('/transcribe', methods=['POST'])
def transcribe_audio_route():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier trouvé'}), 400
    file = request.files['file']
    language_code = request.form.get('language_code', 'fr-FR')
    try:
        transcription = transcrire_audio(file, language_code)
        if transcription:
            return jsonify({'transcription': transcription})
        return jsonify({'error': 'Échec de la transcription'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# New route for long recordings
@app.route('/transcribe_long', methods=['POST'])
def transcribe_long_audio_route():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier trouvé'}), 400
    file = request.files['file']
    language_code = request.form.get('language_code', 'fr-FR')
    try:
        transcription = transcrire_audio_en_chunks(file, language_code)
        return jsonify({'transcription': transcription})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Existing function for short recordings
def transcrire_audio(fichier_audio, language_code):
    audio_data = fichier_audio.read()
    with NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
        temp_file.write(audio_data)
        temp_file_path = temp_file.name

    wav_output_path = 'output_audio.wav'
    ffmpeg.input(temp_file_path).output(wav_output_path).run(overwrite_output=True)

    with open(wav_output_path, 'rb') as audio_file:
        audio_content = audio_file.read()

    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=48000,
        language_code=language_code,
    )
    response = speech_client.recognize(config=config, audio=audio)
    transcription_text = ''.join([result.alternatives[0].transcript for result in response.results])

    os.remove(temp_file_path)
    os.remove(wav_output_path)
    return transcription_text

# New function for long recordings using chunking
def transcrire_audio_en_chunks(fichier_audio, language_code):
    audio_data = fichier_audio.read()
    with NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
        temp_file.write(audio_data)
        temp_file_path = temp_file.name

    wav_output_path = 'output_audio.wav'
    ffmpeg.input(temp_file_path).output(wav_output_path).run(overwrite_output=True)

    # Split audio into chunks
    audio = AudioSegment.from_wav(wav_output_path)
    chunks = make_chunks(audio, 30000)  # 30-second chunks
    transcription_text = ""

    for idx, chunk in enumerate(chunks):
        chunk_path = f"chunk_{idx}.wav"
        chunk.export(chunk_path, format="wav")
        with open(chunk_path, 'rb') as audio_file:
            audio_content = audio_file.read()

        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=48000,
            language_code=language_code,
        )
        response = speech_client.recognize(config=config, audio=audio)
        for result in response.results:
            transcription_text += result.alternatives[0].transcript + " "
        os.remove(chunk_path)  # Clean up chunk files

    os.remove(temp_file_path)
    os.remove(wav_output_path)
    return transcription_text


@app.route('/')
def serve_react_app():
    return send_from_directory(app.static_folder, 'index.html')


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8080)),host='0.0.0.0',debug=True)

