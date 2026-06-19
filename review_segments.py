import os
import csv
import subprocess
from pathlib import Path
import sys

# Try to import audio analysis libraries
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

def get_audio_stats(file_path):
    """Get basic audio statistics using ffmpeg."""
    # Get volume stats
    cmd = ['ffmpeg', '-i', file_path, '-af', 'volumedetect', '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    stats = {}
    for line in result.stderr.split('\n'):
        if 'mean_volume' in line:
            stats['mean_vol'] = line.split(':')[-1].strip()
        if 'max_volume' in line:
            stats['max_vol'] = line.split(':')[-1].strip()
    
    # Get silence ratio (potential indicator of fragmented speech)
    cmd = ['ffmpeg', '-i', file_path, '-af', 'silencedetect=noise=-35dB:d=0.3', '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    silence_count = result.stderr.count('silence_end')
    stats['silence_gaps'] = silence_count
    
    # Get duration
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
           '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        stats['duration'] = float(result.stdout.strip())
    except:
        stats['duration'] = 0
    
    return stats

def analyze_for_issues(stats):
    """Flag potential issues based on audio statistics."""
    flags = []
    
    # High number of silence gaps might indicate fragmented speech
    if stats['silence_gaps'] > 15:
        flags.append("Many pauses (possibly fragmented)")
    
    # Very short duration
    if stats['duration'] < 15:
        flags.append("Very short segment")
    
    return flags

def play_audio(file_path):
    """Play audio file using ffplay."""
    print("  Playing audio... (press 'q' to stop)")
    subprocess.run(['ffplay', '-nodisp', '-autoexit', file_path], 
                   capture_output=True)

def review_segments_interactive():
    """Interactive review of all segments."""
    input_dir = "data/normalized"
    output_csv = "data/segment_review.csv"
    
    wav_files = sorted(Path(input_dir).glob("*.wav"))
    
    if not wav_files:
        print("No WAV files found in", input_dir)
        return
    
    print(f"\n{'='*60}")
    print(f"SEGMENT QUALITY REVIEW")
    print(f"{'='*60}")
    print(f"Found {len(wav_files)} segments to review\n")
    print("Rejection criteria:")
    print("  1. Audience applause/laughter over speech")
    print("  2. Two people talking at once")
    print("  3. Background music audible")
    print("  4. Very fragmented (mostly um, uh)")
    print()
    print("Commands:")
    print("  [k] Keep    [r] Reject    [p] Play audio    [s] Skip (review later)")
    print("  [q] Quit and save progress")
    print(f"{'='*60}\n")
    
    # Load existing reviews if any
    existing_reviews = {}
    if os.path.exists(output_csv):
        with open(output_csv, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_reviews[row['file']] = row
        print(f"Loaded {len(existing_reviews)} existing reviews\n")
    
    reviews = []
    segment_id = 1
    
    for wav_file in wav_files:
        file_name = wav_file.name
        
        # Skip if already decided (keep/reject), but review flagged ones
        if file_name in existing_reviews:
            decision = existing_reviews[file_name]['decision']
            if decision in ['keep', 'reject', 'likely_keep']:
                reviews.append(existing_reviews[file_name])
                segment_id += 1
                continue
        
        print(f"\n[{segment_id}/{len(wav_files)}] {file_name[:60]}...")
        
        # Get audio stats
        stats = get_audio_stats(str(wav_file))
        auto_flags = analyze_for_issues(stats)
        
        print(f"  Duration: {stats['duration']:.1f}s | Silence gaps: {stats['silence_gaps']} | Vol: {stats.get('mean_vol', 'N/A')}")
        
        if auto_flags:
            print(f"  ⚠️  Auto-flags: {', '.join(auto_flags)}")
        
        while True:
            choice = input("  Decision [k/r/p/s/q]: ").strip().lower()
            
            if choice == 'p':
                play_audio(str(wav_file))
                continue
            elif choice == 'k':
                decision = 'keep'
                notes = input("  Notes (optional): ").strip()
                break
            elif choice == 'r':
                decision = 'reject'
                print("  Rejection reasons: 1=applause 2=overlap 3=music 4=fragmented 5=other")
                reason = input("  Reason [1-5]: ").strip()
                reason_map = {
                    '1': 'applause/laughter',
                    '2': 'overlapping speech',
                    '3': 'background music',
                    '4': 'fragmented speech',
                    '5': 'other'
                }
                notes = reason_map.get(reason, reason)
                extra = input("  Additional notes (optional): ").strip()
                if extra:
                    notes += f" - {extra}"
                break
            elif choice == 's':
                decision = 'skip'
                notes = ''
                break
            elif choice == 'q':
                # Save and quit
                save_reviews(reviews, output_csv)
                print(f"\nProgress saved to {output_csv}")
                print(f"Reviewed {len([r for r in reviews if r['decision'] != 'skip'])} segments")
                return
            else:
                print("  Invalid choice. Use k/r/p/s/q")
        
        reviews.append({
            'segment_id': segment_id,
            'file': file_name,
            'decision': decision,
            'notes': notes,
            'duration': f"{stats['duration']:.1f}",
            'silence_gaps': stats['silence_gaps'],
            'auto_flags': '; '.join(auto_flags) if auto_flags else ''
        })
        
        segment_id += 1
    
    save_reviews(reviews, output_csv)
    
    # Summary
    kept = len([r for r in reviews if r['decision'] == 'keep'])
    rejected = len([r for r in reviews if r['decision'] == 'reject'])
    skipped = len([r for r in reviews if r['decision'] == 'skip'])
    
    print(f"\n{'='*60}")
    print(f"REVIEW COMPLETE")
    print(f"{'='*60}")
    print(f"Kept: {kept} | Rejected: {rejected} | Skipped: {skipped}")
    print(f"Results saved to: {output_csv}")

def save_reviews(reviews, output_csv):
    """Save reviews to CSV."""
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['segment_id', 'file', 'decision', 'notes', 'duration', 'silence_gaps', 'auto_flags']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reviews)

def auto_review():
    """Quick automated pre-screening (flags only, no decisions)."""
    input_dir = "data/normalized"
    output_csv = "data/segment_review.csv"
    
    wav_files = sorted(Path(input_dir).glob("*.wav"))
    
    print(f"\n{'='*60}")
    print(f"AUTO PRE-SCREENING {len(wav_files)} SEGMENTS")
    print(f"{'='*60}\n")
    
    reviews = []
    flagged = 0
    
    for i, wav_file in enumerate(wav_files, 1):
        file_name = wav_file.name
        print(f"[{i}/{len(wav_files)}] Analyzing {file_name[:50]}...", end='')
        
        stats = get_audio_stats(str(wav_file))
        auto_flags = analyze_for_issues(stats)
        
        if auto_flags:
            print(f" ⚠️ {', '.join(auto_flags)}")
            flagged += 1
        else:
            print(" ✓")
        
        reviews.append({
            'segment_id': i,
            'file': file_name,
            'decision': 'review' if auto_flags else 'likely_keep',
            'notes': '',
            'duration': f"{stats['duration']:.1f}",
            'silence_gaps': stats['silence_gaps'],
            'auto_flags': '; '.join(auto_flags) if auto_flags else ''
        })
    
    save_reviews(reviews, output_csv)
    
    print(f"\n{'='*60}")
    print(f"PRE-SCREENING COMPLETE")
    print(f"{'='*60}")
    print(f"Clean: {len(wav_files) - flagged} | Flagged for review: {flagged}")
    print(f"Results saved to: {output_csv}")
    print(f"\nRun with --interactive to manually review flagged segments")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        review_segments_interactive()
    else:
        auto_review()
        print("\nTo do full manual review, run: python review_segments.py --interactive")
