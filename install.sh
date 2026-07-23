#!/data/data/com.termux/files/usr/bin/bash
pkg update -y && pkg install python git android-tools -y && pip install requests pycryptodome urllib3
echo -e '#!/data/data/com.termux/files/usr/bin/bash\ncd ~/skyby && python sky.py' > $PREFIX/bin/skyby
chmod +x $PREFIX/bin/skyby
echo "Done! Type: skyby"
