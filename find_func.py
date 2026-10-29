import json
import sys

def main():
    transcript_path = r"C:\Users\Mahendran\.gemini\antigravity\brain\7b612c35-4e37-4b17-98f5-043b5be73238\.system_generated\logs\transcript.jsonl"
    with open(transcript_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i in range(len(lines)-1, -1, -1):
        try:
            data = json.loads(lines[i])
            if data.get('source') == 'MODEL' and 'write_to_file' in str(data):
                continue

            # Let's just find the text "def create_paytm_order"
            if "def create_paytm_order" in str(data):
                content = str(data)
                # Ensure we only print if it contains the actual implementation, not just mentions
                if "body_string =" in content and "initiate_url =" in content:
                    print(f"FOUND IN STEP: {data.get('step_index')}")
                    idx = content.find('def create_paytm_order')
                    print(content[idx-200:idx+3500])
                    break
        except Exception as e:
            pass

if __name__ == "__main__":
    main()
