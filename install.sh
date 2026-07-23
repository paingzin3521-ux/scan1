#!/data/data/com.termux/files/usr/bin/bash

# Update and Install dependencies
echo "[*] Updating and installing dependencies..."
pkg update -y
pkg install python git android-tools -y
pip install requests pycryptodome urllib3

# Create shortcut command
echo "[*] Creating shortcut 'skyby'..."
echo -e "#!/data/data/com.termux/files/usr/bin/bash\ncd $HOME/scan1 && python sky.py \"\$@\"" > $PREFIX/bin/skyby
chmod +x $PREFIX/bin/skyby

echo "------------------------------------"
echo "  Setup Completed Successfully!"
echo "  You can now run the tool by typing: skyby"
echo "------------------------------------"
