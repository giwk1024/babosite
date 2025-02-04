from flask import Flask, request, render_template, send_from_directory
import pandas as pd
from werkzeug.utils import secure_filename
import os
import torch
from openunmix import predict
import stempeg
import librosa
import torchaudio
import numpy as np
import soundfile as sf
from scipy.io.wavfile import write
import warnings
warnings.filterwarnings(action= 'ignore')
import pydub

# Declare a Flask app
app = Flask(__name__,template_folder='template')

app.config['APP_ROOT'] = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(app.config['APP_ROOT'], 'static/uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.mp3', '.wav']

try:
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
except OSError as error:
    print(error)

@app.errorhandler(413)
def too_large(e):
    return "<h1> File is too large </h1> <h3><a href='/'> Try again </a></h3>", 413

@app.route('/', methods=['GET', 'POST'])
def main():
    # If a form is submitted
    if request.method == "POST":

        uploadedfile = request.files['audiovar']
        print(uploadedfile.stream)
        if uploadedfile.filename:
            filename = secure_filename(uploadedfile.filename)
            file_ext = os.path.splitext(filename)[1]
            print(file_ext)
            if file_ext not in app.config['UPLOAD_EXTENSIONS']:
                return "<h1> Invalid file type. <h1> <h3><a href='/'> Try again </a></h3>", 400
            uploadedfile.save(os.path.join(app.config['UPLOAD_FOLDER'],filename))
            print(uploadedfile.filename)

            audio, samplerate = stempeg.read_stems(
                os.path.join(app.config['UPLOAD_FOLDER'],filename),
                sample_rate=44100.0,
                dtype=np.float64
            )
            estimates = predict.separate(
                torch.as_tensor(audio).float(),
                rate=samplerate,
                targets=['vocals','drums', 'bass', 'other'],
                residual=True,
                device='cpu',
            )
            sample_rate = int(samplerate)
            residual  = np.sum([audio.detach().cpu().numpy()[0] for target, audio in estimates.items() if not target=='vocals'],axis=0)
            vocals = estimates['vocals'].detach().cpu().numpy()[0]
            drums = estimates['drums'].detach().cpu().numpy()[0]
            bass = estimates['bass'].detach().cpu().numpy()[0]
            other = estimates['other'].detach().cpu().numpy()[0]

            print("drums type: ",type(drums),"Shape: ", drums.shape)
            print("vocals type: ",type(vocals), "Shape: ", vocals.shape)
            print("bass type: ",type(bass),"Shape: ", bass.shape)
            print("other type: ",type(other), "Shape: ", other.shape)

            d_targetPath = os.path.join(app.config['UPLOAD_FOLDER'], "drums.mp3")
            v_targetPath = os.path.join(app.config['UPLOAD_FOLDER'], "vocals.mp3")
            b_targetPath = os.path.join(app.config['UPLOAD_FOLDER'], "bass.mp3")
            o_targetPath = os.path.join(app.config['UPLOAD_FOLDER'], "other.mp3")

            d1 = np.float16(drums.transpose())
            v1 = np.float16(vocals.transpose())
            b1 = np.float16(bass.transpose())
            o1 = np.float16(other.transpose())

            # data length must be a multiple of '(sample_width * channels)
            song = pydub.AudioSegment(d1.tobytes(), frame_rate=sample_rate, sample_width=2, channels=2)
            song.export(d_targetPath, format="mp3", bitrate="480k")

            song = pydub.AudioSegment(v1.tobytes(), frame_rate=sample_rate, sample_width=2, channels=2)
            song.export(v_targetPath, format="mp3", bitrate="480k")

            song = pydub.AudioSegment(b1.tobytes(), frame_rate=sample_rate, sample_width=2, channels=2)
            song.export(b_targetPath, format="mp3", bitrate="480k")

            song = pydub.AudioSegment(o1.tobytes(), frame_rate=sample_rate, sample_width=2, channels=2)
            song.export(o_targetPath, format="mp3", bitrate="480k")

            return render_template('website.html', filename=filename , vocals = "vocals.mp3", drums = "drums.mp3", bass = "bass.mp3", other = "other.mp3")
    else:
        filename = ""

    return render_template("website.html", filename=filename)

@app.route('/uploads/<filename>')
def uploaded_song(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],filename, as_attachment=True)

# Running the app
if __name__ == '__main__':
    app.run(debug = True)