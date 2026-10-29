import os

views_path = r"C:\jai\api-codingboss\herbal\views.py"
missing_path = r"C:\jai\api-codingboss\missing_functions.py"

with open(missing_path, "r", encoding="utf-8") as f:
    missing_content = f.read()

with open(views_path, "r", encoding="utf-8") as f:
    views_content = f.read()

# find where paytm_callback starts
target = "@csrf_exempt\ndef paytm_callback(request):"
idx = views_content.find(target)

if idx != -1:
    new_content = views_content[:idx] + missing_content + "\n\n" + views_content[idx:]
    with open(views_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Injected successfully!")
else:
    print("Could not find paytm_callback")
