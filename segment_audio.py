import subprocess
import re
import os
from pathlib import Path

def get_audio_duration(file_path):
    """Get duration of audio file in seconds."""
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
           '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())

def get_silence_timestamps(file_path):
    """Detect silence in audio and return list of (start, end) tuples."""
    cmd = ['ffmpeg', '-i', file_path, '-af', 'silencedetect=noise=-40dB:d=0.5', 
           '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    # Parse silence_start and silence_end from stderr
    silences = []
    starts = re.findall(r'silence_start: ([\d.]+)', result.stderr)
    ends = re.findall(r'silence_end: ([\d.]+)', result.stderr)
    
    for start, end in zip(starts, ends):
        silences.append((float(start), float(end)))
    
    return silences

def find_best_cut_point(silences, target_time, tolerance=15):
    """Find silence midpoint closest to target time within tolerance."""
    best_point = None
    best_diff = float('inf')
    
    for start, end in silences:
        midpoint = (start + end) / 2
        diff = abs(midpoint - target_time)
        
        if diff < best_diff and diff <= tolerance:
            best_diff = diff
            best_point = midpoint
    
    return best_point

def segment_audio(input_path, output_dir, segment_duration=60):
    """Segment audio file at silence points near target duration intervals."""
    
    file_name = Path(input_path).stem
    # Clean filename for output
    safe_name = re.sub(r'[^\w\s-]', '', file_name)[:50]
    
    print(f"\n{'='*60}")
    print(f"Processing: {file_name[:60]}...")
    
    # Get total duration
    duration = get_audio_duration(input_path)
    print(f"Total duration: {duration:.1f}s ({duration/60:.1f} min)")
    
    # Get silence timestamps
    silences = get_silence_timestamps(input_path)
    print(f"Found {len(silences)} silence segments")
    
    if not silences:
        print("No silences found, using fixed intervals")
        # Fall back to fixed intervals
        cut_points = list(range(0, int(duration), segment_duration))
        cut_points.append(duration)
    else:
        # Find optimal cut points at silences near 60s intervals
        cut_points = [0]  # Start at beginning
        current_pos = 0
        
        while current_pos < duration - 30:  # Don't create tiny segments at end
            target = current_pos + segment_duration
            
            if target >= duration:
                break
                
            # Find best silence point near target
            best_cut = find_best_cut_point(silences, target, tolerance=20)
            
            if best_cut and best_cut > current_pos + 30:  # Ensure minimum segment size
                cut_points.append(best_cut)
                current_pos = best_cut
            else:
                # No good silence found, try with larger tolerance
                best_cut = find_best_cut_point(silences, target, tolerance=30)
                if best_cut and best_cut > current_pos + 30:
                    cut_points.append(best_cut)
                    current_pos = best_cut
                else:
                    # Still no good point, move forward and try again
                    current_pos = target
        
        cut_points.append(duration)  # End at file end
    
    # Remove duplicates and sort
    cut_points = sorted(set(cut_points))
    
    print(f"Cut points: {len(cut_points)-1} segments")
    for i, cp in enumerate(cut_points):
        print(f"  Point {i}: {cp:.2f}s")
    
    # Create segments
    segments_created = []
    for i in range(len(cut_points) - 1):
        start = cut_points[i]
        end = cut_points[i + 1]
        
        # Skip very short segments
        if end - start < 10:
            continue
        
        output_file = os.path.join(output_dir, f"{safe_name}_seg{i+1:03d}.wav")
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-to', str(end),
            '-i', input_path,
            '-ar', '16000',
            '-ac', '1',
            output_file
        ]
        
        subprocess.run(cmd, capture_output=True)
        
        seg_duration = end - start
        print(f"  Created: seg{i+1:03d} ({start:.1f}s - {end:.1f}s, duration: {seg_duration:.1f}s)")
        segments_created.append(output_file)
    
    return segments_created

def main():
    input_dir = "data/raw"
    output_dir = "data/segments"
    
    os.makedirs(output_dir, exist_ok=True)
    
    wav_files = list(Path(input_dir).glob("*.wav"))
    print(f"Found {len(wav_files)} audio files to process")
    
    all_segments = []
    for wav_file in wav_files:
        segments = segment_audio(str(wav_file), output_dir, segment_duration=60)
        all_segments.extend(segments)
    
    print(f"\n{'='*60}")
    print(f"COMPLETE: Created {len(all_segments)} total segments")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    main()
