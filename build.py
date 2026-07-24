import os
import subprocess
import urllib.request

# URL to the raw original sky.py (stable version)
RAW_URL = "https://raw.githubusercontent.com/paingzin3521-ux/scan1/22939a9/sky.py"

print("[*] Downloading original source code...")
try:
    with urllib.request.urlopen(RAW_URL) as response:
        source_code = response.read().decode('utf-8')
    
    with open("sky.py", "w") as f:
        f.write(source_code)
except Exception as e:
    print(f"[-] Error downloading source: {e}")
    exit(1)

# Create setup.py for Cython
with open("setup.py", "w") as f:
    f.write("""from setuptools import setup
from Cython.Build import cythonize
setup(ext_modules = cythonize("sky.py"))
""")

# Compile to .so
print("[*] Compiling for your device architecture...")
subprocess.run(["python", "setup.py", "build_ext", "--inplace"])

# Cleanup
print("[*] Cleaning up source files...")
# Rename original to backup
if os.path.exists("sky.py"):
    os.rename("sky.py", "sky_source.py")

# Rename the resulting .so file
for file in os.listdir("."):
    if file.startswith("sky.cpython") and file.endswith(".so"):
        os.rename(file, "sky.so")
        break

# Create loader script that calls main()
with open("sky.py", "w") as f:
    f.write("import sky\ntry:\n    sky.main()\nexcept AttributeError:\n    pass\n")

# Final cleanup of sensitive files
if os.path.exists("sky_source.py"):
    os.remove("sky_source.py")
if os.path.exists("sky.c"):
    os.remove("sky.c")
if os.path.exists("setup.py"):
    os.remove("setup.py")

print("[✓] Build complete! Now type 'python sky.py' to start.")
