# Sarvam Audio Processing Pipeline

An end-to-end audio processing pipeline for extracting, segmenting, normalizing, transcribing, and tagging speech audio from YouTube videos using Sarvam AI APIs.
The dataset created from this has been uploaded on HuggingFace and is available at: https://huggingface.co/datasets/Nikita-B7/Motivational_speech_dataset-English_Marathi

## Features

- **YouTube Audio Extraction**: Download audio from YouTube videos as 16kHz mono WAV
- **Silence Detection**: Find natural pause points using ffmpeg
- **Smart Segmentation**: Split audio at silence points into ~60s chunks (never mid-sentence)
- **Loudness Normalization**: Normalize all segments to -16 LUFS for consistent volume
- **Quality Review**: Auto-flag problematic segments (too short, fragmented, etc.)
- **Transcription**: Transcribe audio using Sarvam AI Speech-to-Text API (saaras:v3)
- **Emotion & Style Tagging**: Classify transcripts using Sarvam AI Chat API (sarvam-105b)

## Requirements

### System Dependencies

- **Python 3.10+**
- **ffmpeg** (for audio processing)
  ```powershell
  winget install ffmpeg
  ```
- **yt-dlp** (for YouTube downloads)
  ```powershell
  pip install yt-dlp
  ```

### Python Dependencies

```bash
pip install -r requirements.txt
```

## Project Structure

```
sarvam assignment/
├── segment_audio.py            # Audio segmentation script
├── review_segments.py          # Quality review system
├── transcribe.py               # Sarvam AI transcription
├── emotion_tag.py              # Emotion/style classification
└── README.md
```

## Usage

### 1. Download YouTube Audio

```powershell
yt-dlp --extract-audio --audio-format wav `
  --postprocessor-args "ffmpeg:-ar 16000 -ac 1" `
  -o "data/raw/%(id)s_%(title)s.%(ext)s" `
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

### 2. Segment Audio

```bash
python segment_audio.py "data/raw/VIDEO_FILE.wav"
```

Segments audio at natural silence points (~60s chunks).

### 3. Normalize Loudness

```powershell
Get-ChildItem "data\segments\*.wav" | ForEach-Object {
    ffmpeg -i $_.FullName -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 16000 -ac 1 "data\normalized\$($_.Name)"
}
```

### 4. Review Segments

```bash
# Auto-review (flags problematic segments)
python review_segments.py --auto-only

# Interactive review
python review_segments.py --interactive
```

### 5. Transcribe

```bash
python transcribe.py
```

Transcribes all approved segments using Sarvam AI Speech-to-Text API.

### 6. Emotion & Style Tagging

```bash
python emotion_tag.py
```

Tags each transcript with:
- **Emotion**: neutral, happy, sad, angry, excited, fearful, surprised
- **Style**: formal, conversational, storytelling, motivational, poetic, instructional, news-reading

## Configuration

Set your Sarvam AI API key in the scripts:
```python
SARVAM_API_KEY = "your_api_key_here"
```

### Language Mapping

The pipeline auto-detects language based on video ID:
- `mr-IN` - Marathi
- `hi-IN` - Hindi  
- `en-IN` - English (default)

## API Limits

- Sarvam Speech-to-Text: **30 seconds max** per request (auto-chunked)
- Audio format: 16kHz mono WAV

## Output Files

### transcriptions.csv
| Column | Description |
|--------|-------------|
| segment_id | Segment identifier |
| file | Audio filename |
| language | Language code |
| transcript | Transcribed text |
| success | Whether transcription succeeded |
| error | Error message if failed |

### transcriptions_tagged.csv
Same as above, plus:
| Column | Description |
|--------|-------------|
| emotion | Detected emotion tag |
| style | Detected speaking style |

## License

MIT
