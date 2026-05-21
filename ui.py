import streamlit as st
import os
import time
# Mengimport fungsi backend terbaru dari app.py
from app import start_live_recording, stop_live_recording, transcribe_audio, query_qwen, export_to_docx, UPLOAD_DIR

st.set_page_config(
    page_title="Transkripku - Local AI",
    page_icon="🎙️",
    layout="wide"
)

# ==========================================
# 1. GLOBAL CSS (TEKS PUTIH MENYALA)
# ==========================================
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background-color: #0A0C10;
    }
    
    * {
        color: #FFFFFF !important;
    }
    
    .stTextArea textarea, .stTextInput input {
        background-color: #171A21 !important;
        color: #FFFFFF !important;
        border: 2px solid #4A5264 !important;
        border-radius: 6px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
    }
    
    .stTextArea textarea:focus, .stTextInput input:focus {
        border: 2px solid #00D2FF !important;
        box-shadow: 0 0 8px rgba(0, 210, 255, 0.6) !important;
    }

    div.stButton > button:first-child {
        background-color: #232834;
        color: #FFFFFF !important;
        font-weight: 700;
        font-size: 15px !important;
        border-radius: 6px;
        border: 2px solid #5A657C;
        padding: 0.6rem 1rem;
    }
    
    div.stButton > button:first-child:hover {
        background-color: #2F3646;
        border: 2px solid #00D2FF;
    }
    
    .stAlert {
        background-color: #1A1F2C !important;
        border: 2px solid #3A4358 !important;
    }
    
    div[data-baseweb="select"] > div {
        background-color: #171A21 !important;
        border: 2px solid #4A5264 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Inisialisasi Memori Status Aplikasi
if "transcript_result" not in st.session_state:
    st.session_state.transcript_result = ""
if "ai_analysis" not in st.session_state:
    st.session_state.ai_analysis = ""
if "is_recording" not in st.session_state:
    st.session_state.is_recording = False
if "start_time" not in st.session_state:
    st.session_state.start_time = 0

st.title("🎙️ Transkripku")
st.subheader("Sistem Notulensi Teams dan Ringkasan Rapat Otomatis dengan AI Lokal")
st.markdown("---")

col1, col2 = st.columns([1, 1.2], gap="large")

with col1:
    st.markdown("### 🛠️ Input Control")
    input_mode = st.radio("Pilih Metode Input Audio:", ["Live Recording (MS Teams)", "Upload File Audio (.wav/.mp3)"])
    
    # ----------------------------------------------------
    # FITUR TERBARU: TOMBOL START & STOP AUDIO FLEKSIBEL
    # ----------------------------------------------------
    if input_mode == "Live Recording (MS Teams)":
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Kondisi 1: Jika Belum Mulai Merekam (Tampilkan Tombol Start)
        if not st.session_state.is_recording:
            st.info("💡 Klik tombol di bawah untuk mulai merekam audio rapat MS Teams secara real-time.")
            if st.button("🔴 Mulai Rekam (Start)", use_container_width=True):
                start_live_recording()
                st.session_state.is_recording = True
                st.session_state.start_time = time.time()
                st.rerun()  # Muat ulang halaman UI untuk memperbarui status tombol
                
        # Kondisi 2: Jika Sedang Merekam (Tampilkan Tombol Stop)
        else:
            elapsed_seconds = int(time.time() - st.session_state.start_time)
            st.warning(f"⏳ Perekaman sedang berjalan aktif... (Berjalan sekitar: {elapsed_seconds} detik)")
            
            if st.button("⏹️ Selesai Rekam (Stop & Transkrip)", use_container_width=True):
                st.session_state.is_recording = False
                
                with st.spinner("Menghentikan rekaman dan menyimpan file audio..."):
                    audio_path = stop_live_recording("live_teams_record.wav")
                    
                with st.spinner("Mentranskrip rekaman suara via Faster-Whisper Lokal..."):
                    st.session_state.transcript_result = transcribe_audio(audio_path)
                    
                st.toast("Proses transkrip audio sukses!", icon="✅")
                st.rerun()
            
            # Tombol kecil rahasia untuk menyegarkan info durasi detik di atas jika diinginkan
            if st.button("🔄 Perbarui Status Waktu", use_container_width=False):
                st.rerun()
            
    else:
        st.markdown("<br>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Unggah File Audio Rapat", type=["wav", "mp3", "m4a"])
        
        if uploaded_file is not None:
            if st.button("Proses File Audio", use_container_width=True):
                save_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                
                with st.spinner("Mentranskrip file audio..."):
                    st.session_state.transcript_result = transcribe_audio(save_path)
                st.toast("File audio berhasil ditranskrip!", icon="✅")

    st.markdown("---")
    st.markdown("### 📝 Hasil Transkrip Mentah")
    st.session_state.transcript_result = st.text_area(
        "Edit teks jika diperlukan sebelum dianalisis AI:", 
        value=st.session_state.transcript_result, 
        height=250
    )

with col2:
    st.markdown("### 🤖 Ringkasan & Notulensi (Ollama Qwen 2.5)")
    default_prompt = (
        "saya bekerja di Direktorat Jenderal Pajak (DJP). Bertindaklah sebagai 3 role Sekretaris, yaitu di Direktorat Data dan Informasi Perpajakan (Direktorat DIP), Subdirektorat Tata Kelola data dan Informasi (Subdit TKDI), dan seksi Perencanaan Strategis Data dan Informasi (Seksi PSDI). Buat ringkasan eksekutif "
        "yang detail dari teks transkrip rapat di bawah dengan format:\n"
        "1. Topik Utama Pembahasan\n"
        "2. Poin-Poin Penting Diskusi, utamakan yang terkait tengan DIP, TKDI, PSDI\n"
        "3. Action Items (Siapa melakukan apa), utamakan yang terkait tengan DIP, TKDI, PSDI\n"
        "4. Kesimpulan Akhir Rapat.\n\n"
        "Gunakan Bahasa Indonesia formal yang lazim digunakan di instansi pemerintah."
    )
    
    ai_prompt = st.text_area("Instruksi Perintah AI (Prompt):", value=default_prompt, height=120)
    
    if st.button("Generate Notulensi Rapat", use_container_width=True):
        if not st.session_state.transcript_result.strip():
            st.error("Gagal: Lakukan transkrip teks/isi teks mentah terlebih dahulu!")
        else:
            with st.spinner("Ollama sedang menganalisis transkrip..."):
                st.session_state.ai_analysis = query_qwen(st.session_state.transcript_result, ai_prompt)
            st.toast("Notulensi berhasil dibuat!", icon="✨")
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.session_state.ai_analysis:
        st.markdown("#### 📑 Hasil Ringkasan Resmi:")
        st.info(st.session_state.ai_analysis)
        
        st.markdown("---")
        if st.button("📥 Download Notulensi sebagai File Word (.docx)", use_container_width=True):
            if not st.session_state.ai_analysis.strip():
                st.error("Gagal: Belum ada hasil ringkasan AI untuk diunduh!")
            else:
                with st.spinner("Menyusun dokumen Word..."):
                    # CUKUP KIRIM 1 PARAMETER SAJA (Hasil Ringkasan AI)
                    docx_file = export_to_docx(st.session_state.ai_analysis)
                
                # Mengambil nama file asli (summary1.docx, summary2.docx, dst.) untuk diunduh user
                download_name = os.path.basename(docx_file)
                
                with open(docx_file, "rb") as f:
                    st.download_button(
                        label=f"📂 Klik di Sini untuk Menyimpan {download_name}",
                        data=f,
                        file_name=download_name, # Nama file dinamis mengikuti summary1, summary2...
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
