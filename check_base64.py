"""
Run this to verify base64 image output matches what the API returns.
Usage: python check_base64.py
"""
import os
import base64
import sys

# Path to frames directory
frames_dir = os.path.join(os.path.dirname(__file__), "media", "frames")

# Get the most recent frame file
try:
    files = sorted(
        [f for f in os.listdir(frames_dir) if f.endswith(".jpeg")],
        key=lambda f: os.path.getmtime(os.path.join(frames_dir, f)),
        reverse=True
    )
except Exception as e:
    print(f"❌ Cannot read frames dir: {e}")
    sys.exit(1)

if not files:
    print("❌ No frame files found in media/frames/")
    sys.exit(1)

latest_file = os.path.join(frames_dir, files[0])
print(f"\n📁 Latest frame: {files[0]}")
print(f"📦 File size: {os.path.getsize(latest_file)} bytes")

# Read and base64 encode
with open(latest_file, "rb") as f:
    raw = f.read()

b64 = base64.b64encode(raw).decode("utf-8")
data_url = f"data:image/jpeg;base64,{b64}"

print(f"\n📏 Base64 string length: {len(b64)} chars")
print(f"🔍 First 80 chars: {b64[:80]}")
print(f"\n✅ Full data URL prefix: {data_url[:50]}")

# Validate JPEG magic bytes
if raw[:2] == b'\xff\xd8':
    print("\n✅ Valid JPEG — starts with FF D8 (JPEG magic bytes)")
else:
    print(f"\n❌ NOT a valid JPEG — first bytes: {raw[:4].hex()}")
    print("   This file may be corrupted or not a real image.")

# Check all files for size anomalies
print(f"\n📊 File size breakdown across all {len(files)} frames:")
sizes = [os.path.getsize(os.path.join(frames_dir, f)) for f in files]
size_1027 = sum(1 for s in sizes if s == 1027)
size_ok = sum(1 for s in sizes if s > 2000)
print(f"   - 1027 bytes (possibly blank/corrupted): {size_1027}")
print(f"   - >2000 bytes (likely real images)     : {size_ok}")
print(f"   - Other sizes                          : {len(files) - size_1027 - size_ok}")

if size_1027 > size_ok:
    print("\n⚠️  WARNING: Most frames are exactly 1027 bytes.")
    print("   This suggests the camera is sending blank/corrupt frames.")
    print("   The base64 will encode correctly, but the image will appear blank.")
