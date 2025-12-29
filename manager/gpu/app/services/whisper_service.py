from faster_whisper import WhisperModel
import os

MODEL_DIR = os.getenv("MODEL_PATH")

model = WhisperModel(
    os.path.join(MODEL_DIR, "faster-whisper-large-v3"),
    device="cuda",
    compute_type="float16"
)

def transcribe_audio(
    audio_path: str,
    language: str = "ko",
):
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    text = " ".join(seg.text for seg in segments)

    return {
        "language": info.language,
        "duration": info.duration,
        "text": text,
    }
