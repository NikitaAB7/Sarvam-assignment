"""
Prepare dataset for HuggingFace upload.
Copies normalized audio files and creates proper metadata.
"""
import os
import csv
import shutil
import json
from pathlib import Path

# Paths
SOURCE_AUDIO = "data/normalized"
SOURCE_CSV = "data/transcriptions_tagged.csv"
OUTPUT_DIR = "hf_dataset"
AUDIO_DIR = os.path.join(OUTPUT_DIR, "data", "audio")

def get_duration(file_path):
    """Get audio duration using ffprobe."""
    import subprocess
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0.0

def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    
    # Read transcriptions
    with open(SOURCE_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Processing {len(rows)} samples...")
    
    # Prepare metadata
    metadata = []
    audio_files_copied = 0
    
    for i, row in enumerate(rows, 1):
        orig_file = row.get('file', '')
        transcript = row.get('transcript', '')
        language = row.get('language', 'en-IN')
        emotion = row.get('emotion', 'neutral')
        style = row.get('style', 'conversational')
        
        # Skip if no transcript
        if not transcript or row.get('success', 'True') != 'True':
            continue
        
        # Find source audio file
        # Handle different path formats in CSV
        if 'normalized' in orig_file:
            # Already has path
            audio_name = os.path.basename(orig_file)
            source_path = orig_file
        else:
            audio_name = orig_file
            source_path = os.path.join(SOURCE_AUDIO, orig_file)
        
        # Check if file exists
        if not os.path.exists(source_path):
            # Try finding in normalized folder
            matches = list(Path(SOURCE_AUDIO).glob(f"*{audio_name.split('_')[-1]}*"))
            if matches:
                source_path = str(matches[0])
                audio_name = matches[0].name
            else:
                print(f"  Warning: Audio not found for {orig_file}")
                continue
        
        # Create clean filename
        clean_name = f"sample_{i:04d}.wav"
        dest_path = os.path.join(AUDIO_DIR, clean_name)
        
        # Copy audio file
        if not os.path.exists(dest_path):
            shutil.copy2(source_path, dest_path)
            audio_files_copied += 1
        
        # Get duration
        duration = get_duration(dest_path)
        
        # Map language codes to full names
        lang_map = {
            'mr-IN': 'Marathi',
            'hi-IN': 'Hindi',
            'en-IN': 'English'
        }
        
        # Add to metadata
        metadata.append({
            'file_name': f"audio/{clean_name}",
            'transcript': transcript,
            'language': lang_map.get(language, language),
            'language_code': language,
            'emotion': emotion,
            'style': style,
            'duration': round(duration, 2),
            'original_file': audio_name
        })
        
        if i % 10 == 0:
            print(f"  Processed {i}/{len(rows)}")
    
    # Write metadata CSV (HuggingFace format)
    metadata_path = os.path.join(OUTPUT_DIR, "data", "metadata.csv")
    with open(metadata_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['file_name', 'transcript', 'language', 'language_code', 'emotion', 'style', 'duration', 'original_file']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metadata)
    
    # Also write JSONL format (alternative)
    jsonl_path = os.path.join(OUTPUT_DIR, "data", "metadata.jsonl")
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for item in metadata:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    # Calculate stats
    total_duration = sum(m['duration'] for m in metadata)
    lang_counts = {}
    emotion_counts = {}
    style_counts = {}
    
    for m in metadata:
        lang = m['language']
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        emotion_counts[m['emotion']] = emotion_counts.get(m['emotion'], 0) + 1
        style_counts[m['style']] = style_counts.get(m['style'], 0) + 1
    
    print(f"\n{'='*50}")
    print(f"DATASET PREPARED")
    print(f"{'='*50}")
    print(f"Total samples: {len(metadata)}")
    print(f"Audio files copied: {audio_files_copied}")
    print(f"Total duration: {total_duration/60:.1f} minutes")
    print(f"\nLanguage distribution:")
    for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
        print(f"  {lang}: {count}")
    print(f"\nEmotion distribution:")
    for emotion, count in sorted(emotion_counts.items(), key=lambda x: -x[1]):
        print(f"  {emotion}: {count}")
    print(f"\nStyle distribution:")
    for style, count in sorted(style_counts.items(), key=lambda x: -x[1]):
        print(f"  {style}: {count}")
    print(f"\nOutput:")
    print(f"  {metadata_path}")
    print(f"  {jsonl_path}")
    print(f"  {AUDIO_DIR}/ ({len(metadata)} files)")

if __name__ == "__main__":
    main()
