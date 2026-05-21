# ==========================================
# 1. BYPASS SSL (WAJIB DI BARIS PALING ATAS)
# ==========================================
import ssl
import os
ssl._create_default_https_context = ssl._create_unverified_context

# ==========================================
# 2. IMPORT LIBRARY LAINNYA
# ==========================================
import requests
import json
from faster_whisper import WhisperModel
import soundcard as sc
import soundfile as sf
from docx import Document

# ==========================================
# 3. KONFIGURASI FOLDER LOKAL
# ==========================================
UPLOAD_DIR = "local_storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 4. Inisialisasi Faster-Whisper (Sekarang menggunakan model medium)
print("Loading Whisper Model (Medium)...")
import os
from faster_whisper import WhisperModel

# Pastikan path absolut terbentuk dengan benar menggunakan format Windows native
base_dir = os.path.dirname(os.path.abspath(__file__))
local_model_path = os.path.normpath(os.path.join(base_dir, "models", "whisper-medium"))

print(f"Memuat model dari folder lokal: {local_model_path}")

# SOLUSI: Menggunakan parameter model_path secara eksplisit jika versi library mendukung,
# ATAU memastikan string path diakhiri dengan separator yang jelas agar dikenali sebagai direktori.
if not os.path.isdir(local_model_path):
    raise FileNotFoundError(f"Folder model tidak ditemukan di {local_model_path}")

# Tambahkan double quotes atau pastikan objek berupa string path absolut yang bersih
model_stt = WhisperModel(str(local_model_path), device="cpu", compute_type="int8")

# ... (sisa kode fungsi record_teams_audio, query_qwen, dll tetap sama ke bawah)

# 2. Fungsi Perekaman Audio dari Microsoft Teams (Loopback)
import sounddevice as sd
from scipy.io import wavfile
import numpy as np

# Variabel global untuk menyimpan data rekaman sementara di memori
audio_buffer = []
audio_stream = None

def start_live_recording():
    """Fungsi untuk membuka jalur audio dan mulai merekam di latar belakang"""
    global audio_buffer, audio_stream
    audio_buffer = []  # Kosongkan sisa rekaman lama
    sample_rate = 16000
    target_device_id = None

    # Cari perangkat VB-Cable
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if "cable" in dev['name'].lower() or "virtual" in dev['name'].lower():
            if dev['max_input_channels'] > 0:
                target_device_id = idx
                break
                
    if target_device_id is None:
        target_device_id = sd.default.device[0]

    print(f"🎙️ [Mulai] Menghubungkan ke: {sd.query_devices(target_device_id)['name']}")
    
    # Fungsi callback yang otomatis dipanggil Windows setiap ada data suara masuk
    def callback(indata, frames, time, status):
        if status:
            print(status)
        audio_buffer.append(indata.copy())

    # Membuka saluran aliran audio secara terus-menerus
    audio_stream = sd.InputStream(
        samplerate=sample_rate, 
        channels=1, 
        dtype='float32', 
        device=target_device_id, 
        callback=callback
    )
    audio_stream.start()
    print("▶️ Perekaman latar belakang aktif...")

def stop_live_recording(filename="live_teams_record.wav"):
    """Fungsi untuk menghentikan perekaman dan langsung menyimpan hasilnya ke file"""
    global audio_buffer, audio_stream
    
    if audio_stream is not None:
        audio_stream.stop()
        audio_stream.close()
        audio_stream = None
        print("⏹️ Perekaman dihentikan oleh pengguna.")
    
    if len(audio_buffer) == 0:
        print("⚠️ Tidak ada data audio yang tertangkap.")
        # Buat file kosong darurat agar tidak crash
        wavfile.write(filename, 16000, np.zeros(16000, dtype=np.int16))
        return filename

    # Gabungkan seluruh potongan data dari memori buffer
    recording_data = np.concatenate(audio_buffer, axis=0)
    
    # Konversi ke format PCM Int16 standar Whisper
    audio_int16 = (recording_data * 32767).astype(np.int16)
    
    # Simpan file secara lokal
    wavfile.write(filename, 16000, audio_int16)
    print(f"💾 File sukses disimpan: {filename}")
    return filename

# 3. Fungsi Transkrip Offline
def transcribe_audio(file_path):
    segments, info = model_stt.transcribe(file_path, beam_size=5, language="id")
    
    full_transcript = []
    for segment in segments:
        # Format tiruan Diarization (Untuk implementasi penuh pyannote membutuhkan token HuggingFace secara offline)
        # Di sini kita buat struktur segmentasi dasar
        text_line = f"[Pembicara] [{segment.start:.2f}s - {segment.end:.2f}s]: {segment.text}"
        full_transcript.append(text_line)
        
    return "\n".join(full_transcript)

# 4. Fungsi Local LLM via Ollama (Qwen 2.5)
def query_qwen(prompt, system_prompt="Kamu adalah asisten rapat strategis yang handal."):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:3b",
        "prompt": f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n",
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        return response.json().get("response", "Gagal mendapatkan respon dari Qwen.")
    except Exception as e:
        return f"Error koneksi ke Ollama: {str(e)}"

# 5. Fungsi Ekspor ke DOCX
def export_to_docx(ai_analysis):
    import docx
    import os
    
    # Tentukan folder penyimpanan lokal
    storage_dir = "local_storage"
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)
        
    # ----------------------------------------------------
    # SISTEM PENAMAAN OTOMATIS: summary1, summary2, dst.
    # ----------------------------------------------------
    counter = 1
    while True:
        filename = f"summary{counter}.docx"
        path = os.path.join(storage_dir, filename)
        # Jika file dengan nama tersebut belum ada, gunakan nama ini
        if not os.path.exists(path):
            break
        counter += 1 # Jika sudah ada, naikkan angka (summary2, summary3...)

    # Membuat dokumen Word baru
    doc = docx.Document()
    
    # Menambahkan Judul di dalam Dokumen Word
    doc.add_heading("Ringkasan Resmi Hasil Rapat", level=1)
    
    # Memasukkan isi teks hasil generate AI baris demi baris secara rapi
    for line in ai_analysis.split('\n'):
        if line.strip().startswith('###'):
            doc.add_heading(line.replace('###', '').strip(), level=2)
        elif line.strip().startswith('####'):
            doc.add_heading(line.replace('####', '').strip(), level=3)
        elif line.strip():
            doc.add_paragraph(line.strip())
            
    # Menyimpan dokumen Word
    doc.save(path)
    print(f"💾 File sukses dibuat dengan nama: {path}")
    return path
