import csv
import json
import time
from sarvamai import SarvamAI

# Sarvam AI Configuration
SARVAM_API_KEY = "sk_b9laur4a_Yp5aJLLvSlLvgSOpfHrl4PAr"
client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

SYSTEM_PROMPT = """You are a speech emotion and style classifier. Given a transcript, analyze it and return ONLY a JSON object with two fields:
- "emotion": one of [neutral, happy, sad, angry, excited, fearful, surprised]
- "style": one of [formal, conversational, storytelling, motivational, poetic, instructional, news-reading]

Rules:
- Choose the DOMINANT emotion in the transcript
- Choose the BEST matching style
- Return ONLY valid JSON, no other text
- Example: {"emotion": "excited", "style": "motivational"}"""

def classify_transcript(transcript):
    """Classify a transcript for emotion and style using Sarvam chat API."""
    try:
        # Truncate very long transcripts to first 1000 chars for efficiency
        text = transcript[:1000] if len(transcript) > 1000 else transcript
        
        response = client.chat.completions(
            model="sarvam-105b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Classify this transcript:\n\n{text}"}
            ],
            temperature=0.1,
            max_tokens=50
        )
        
        # Extract the response content
        content = response.choices[0].message.content
        if content is None:
            return "neutral", "conversational"
        content = content.strip()
        
        # Parse JSON from response
        # Handle cases where model might wrap in markdown
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        result = json.loads(content)
        return result.get("emotion", "neutral"), result.get("style", "conversational")
    
    except json.JSONDecodeError as e:
        print(f"    JSON parse error: {content}")
        return "neutral", "conversational"
    except Exception as e:
        print(f"    API error: {e}")
        return "neutral", "conversational"

def main():
    # Read existing transcriptions
    input_file = "data/transcriptions.csv"
    output_file = "data/transcriptions_tagged.csv"
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Processing {len(rows)} transcriptions...\n")
    
    results = []
    for i, row in enumerate(rows, 1):
        transcript = row.get('transcript', '')
        seg_id = row.get('segment_id', str(i))
        if not transcript or row.get('success', 'True') != 'True':
            print(f"[{i}/{len(rows)}] Skipping {seg_id} (no transcript)")
            row['emotion'] = ''
            row['style'] = ''
            results.append(row)
            continue
        
        print(f"[{i}/{len(rows)}] {seg_id}...", end='', flush=True)
        
        emotion, style = classify_transcript(transcript)
        row['emotion'] = emotion
        row['style'] = style
        results.append(row)
        
        print(f" -> {emotion}, {style}")
        
        # Delay to avoid rate limiting
        time.sleep(0.8)
    
    # Write results to new CSV
    fieldnames = ['segment_id', 'file', 'language', 'transcript', 'success', 'error', 'emotion', 'style']
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in results:
            # Ensure all fields exist
            for field in fieldnames:
                if field not in row:
                    row[field] = ''
            writer.writerow(row)
    
    print(f"\n✓ Saved to {output_file}")
    
    # Print summary
    emotions = {}
    styles = {}
    for row in results:
        e = row.get('emotion', 'unknown')
        s = row.get('style', 'unknown')
        emotions[e] = emotions.get(e, 0) + 1
        styles[s] = styles.get(s, 0) + 1
    
    print("\nEmotion distribution:")
    for e, count in sorted(emotions.items(), key=lambda x: -x[1]):
        print(f"  {e}: {count}")
    
    print("\nStyle distribution:")
    for s, count in sorted(styles.items(), key=lambda x: -x[1]):
        print(f"  {s}: {count}")

if __name__ == "__main__":
    main()
