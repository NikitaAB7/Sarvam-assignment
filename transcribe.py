import os
import csv
import time
import subprocess
import tempfile
from pathlib import Path
from sarvamai import SarvamAI

# Refresh PATH to include ffmpeg/ffprobe
os.environ['PATH'] = os.environ.get('PATH', '') + ';C:\\Users\\Anant\\AppData\\Local\\Microsoft\\WinGet\\Links'

# Sarvam AI Configuration
SARVAM_API_KEY = "sk_b9laur4a_Yp5aJLLvSlLvgSOpfHrl4PAr"
MAX_DURATION = 30  # API limit in seconds

# Initialize client
client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

# Language mapping based on video IDs
LANGUAGE_MAP = {
    "ebFe4p-i4WE": "mr-IN",   # Marathi - Josh Talks Marathi
    "J6VwLFDD-T0": "mr-IN",   # Marathi - Ti Phulrani monologue
    "LeIoaKLG2Js": "en-IN",   # English - TEDx
    "TqxxCYnAxo8": "en-IN",   # English - TEDx
    "rW1yhhy07fg": "hi-IN",   # Hindi - Instagram story
}

def get_language_code(filename):
    """Determine language code from filename."""
    for video_id, lang in LANGUAGE_MAP.items():
        if video_id in filename:
            return lang
    return "en-IN"  # Default to English

def get_audio_duration(file_path):
    """Get audio duration in seconds."""
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0

def split_audio_chunk(file_path, start, duration, temp_dir):
    """Extract a chunk from audio file."""
    chunk_path = os.path.join(temp_dir, f"chunk_{start:.1f}.wav")
    cmd = ['ffmpeg', '-y', '-ss', str(start), '-t', str(duration),
           '-i', file_path, '-ar', '16000', '-ac', '1', chunk_path]
    subprocess.run(cmd, capture_output=True)
    return chunk_path

def transcribe_chunk(file_path, language_code):
    """Transcribe a single audio chunk using Sarvam AI SDK."""
    try:
        with open(file_path, "rb") as audio_file:
            response = client.speech_to_text.transcribe(
                file=audio_file,
                model="saaras:v3",
                language_code=language_code
            )
        
        transcript = response.transcript if hasattr(response, 'transcript') else str(response)
        return {
            "success": True,
            "transcript": transcript
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "transcript": ""
        }

def transcribe_audio(file_path, language_code):
    """Transcribe audio file, splitting into chunks if needed."""
    duration = get_audio_duration(file_path)
    
    if duration <= MAX_DURATION:
        # Direct transcription for short files
        return transcribe_chunk(file_path, language_code)
    
    # Split into chunks for longer files
    full_transcript = []
    chunk_start = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        while chunk_start < duration:
            chunk_duration = min(MAX_DURATION, duration - chunk_start)
            
            # Skip very short final chunks
            if chunk_duration < 2:
                break
            
            chunk_path = split_audio_chunk(file_path, chunk_start, chunk_duration, temp_dir)
            result = transcribe_chunk(chunk_path, language_code)
            
            if result["success"] and result["transcript"]:
                full_transcript.append(result["transcript"])
            elif not result["success"]:
                return result  # Return error
            
            chunk_start += MAX_DURATION
            time.sleep(0.3)  # Rate limiting between chunks
    
    return {
        "success": True,
        "transcript": " ".join(full_transcript)
    }

def load_approved_segments(review_csv):
    """Load list of approved segments from review CSV."""
    approved = []
    if os.path.exists(review_csv):
        with open(review_csv, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Include both 'keep' and 'likely_keep' decisions
                if row['decision'] in ['keep', 'likely_keep']:
                    approved.append(row['file'])
    return approved

def main():
    input_dir = "data/normalized"
    review_csv = "data/segment_review.csv"
    output_csv = "data/transcriptions.csv"
    
    # Load approved segments
    approved_files = load_approved_segments(review_csv)
    
    if not approved_files:
        # If no review file, transcribe all
        approved_files = [f.name for f in Path(input_dir).glob("*.wav")]
    
    print(f"\n{'='*60}")
    print(f"SARVAM AI TRANSCRIPTION")
    print(f"{'='*60}")
    print(f"Segments to transcribe: {len(approved_files)}")
    print(f"Output: {output_csv}")
    print(f"{'='*60}\n")
    
    # Prepare output CSV
    results = []
    successful = 0
    failed = 0
    
    for i, filename in enumerate(approved_files, 1):
        file_path = os.path.join(input_dir, filename)
        
        if not os.path.exists(file_path):
            print(f"[{i}/{len(approved_files)}] ⚠️ File not found: {filename[:50]}")
            continue
        
        language_code = get_language_code(filename)
        print(f"[{i}/{len(approved_files)}] Transcribing ({language_code}): {filename[:50]}...", end='', flush=True)
        
        result = transcribe_audio(file_path, language_code)
        
        if result["success"]:
            print(f" ✓")
            successful += 1
            # Preview first 100 chars
            preview = result["transcript"][:100].replace('\n', ' ')
            print(f"    → \"{preview}...\"")
        else:
            print(f" ✗ {result['error'][:50]}")
            failed += 1
        
        results.append({
            "segment_id": i,
            "file": filename,
            "language": language_code,
            "transcript": result.get("transcript", ""),
            "success": result["success"],
            "error": result.get("error", "")
        })
        
        # Rate limiting - wait between requests
        if i < len(approved_files):
            time.sleep(0.5)
    
    # Save results to CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['segment_id', 'file', 'language', 'transcript', 'success', 'error']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n{'='*60}")
    print(f"TRANSCRIPTION COMPLETE")
    print(f"{'='*60}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Results saved to: {output_csv}")
    
    # Calculate estimated cost
    total_duration = sum([float(r.get('duration', 60)) for r in results]) if results else 0
    print(f"\nTotal audio processed: ~{len(approved_files)} minutes")

if __name__ == "__main__":
    main()
