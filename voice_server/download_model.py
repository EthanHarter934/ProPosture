import os
import time
from huggingface_hub import snapshot_download
from huggingface_hub.utils import HfHubHTTPError

# Use the reliable HF mirror to avoid connection resets
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

if __name__ == "__main__":
    print("Downloading VoxCPM2 model (using HF mirror)...")
    
    max_retries = 20
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\nAttempt {attempt}/{max_retries}...")
            snapshot_download(
                repo_id="openbmb/VoxCPM2", 
                resume_download=True,
                local_files_only=False
            )
            print("Download completed successfully!")
            break
        except Exception as e:
            print(f"\nDownload interrupted: {e}")
            if attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Failed to download model after multiple attempts.")
