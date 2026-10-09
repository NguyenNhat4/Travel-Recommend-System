import os
import sys
import time
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor

url = "https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/model.safetensors"
blob_dir = r"C:\Users\tqanh\.cache\huggingface\hub\models--intfloat--multilingual-e5-small\blobs"
blob_path = os.path.join(blob_dir, "1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477")
snap_path = r"C:\Users\tqanh\.cache\huggingface\hub\models--intfloat--multilingual-e5-small\snapshots\614241f622f53c4eeff9890bdc4f31cfecc418b3\model.safetensors"

total_size = 470641600
num_threads = 16
chunk_size = (total_size + num_threads - 1) // num_threads

print(f"Resolving CDN direct URL...", flush=True)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req)
cdn_url = resp.geturl()
print(f"Resolved CDN URL: {cdn_url[:75]}...", flush=True)

# Pre-allocate blob_path
os.makedirs(blob_dir, exist_ok=True)
with open(blob_path, "wb") as f:
    f.truncate(total_size)

downloaded = [0] * num_threads

def download_part(idx):
    start = idx * chunk_size
    end = min(start + chunk_size - 1, total_size - 1)
    expected = end - start + 1
    
    r_req = urllib.request.Request(cdn_url, headers={
        "Range": f"bytes={start}-{end}",
        "User-Agent": "Mozilla/5.0"
    })
    
    with urllib.request.urlopen(r_req, timeout=30) as r, open(blob_path, "r+b") as out_f:
        out_f.seek(start)
        cur = 0
        while cur < expected:
            block = r.read(min(256 * 1024, expected - cur))
            if not block:
                break
            out_f.write(block)
            cur += len(block)
            downloaded[idx] = cur
    print(f"Part {idx:02d} done: {cur} bytes", flush=True)

print(f"Starting {num_threads} concurrent workers...", flush=True)
t0 = time.time()
with ThreadPoolExecutor(max_workers=num_threads) as pool:
    list(pool.map(download_part, range(num_threads)))

print(f"Download complete in {round(time.time() - t0, 1)}s. Verifying file size...", flush=True)
act_size = os.path.getsize(blob_path)
if act_size == total_size:
    print(f"Size verified: {act_size} bytes. Copying to snapshot...", flush=True)
    shutil.copyfile(blob_path, snap_path)
    print("DONE! model.safetensors is ready!", flush=True)
else:
    print(f"Error: expected {total_size}, got {act_size}", flush=True)
    sys.exit(1)
