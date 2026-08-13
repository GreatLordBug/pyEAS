# pyEAS
## DEPENDENCIES
figure it out bozo, but if you insist:
MUST BE LINUX
for Debian-Based:
``` bash
#!/bin/bash
set -e
sudo apt-get update
sudo apt-get install -y python3-tk espeak-ng python3-pip python3-dev build-essential libasound2-dev libjack-jackd2-dev libsndfile1
python3 -m pip install --upgrade pip --break-system-packages || python3 -m pip install --upgrade pip
python3 -m pip install numpy soundfile sounddevice requests --break-system-packages || python3 -m pip install numpy soundfile sounddevice requests
```
for Fedora/REHL Based:
``` bash
#!/bin/bash
set -e
sudo dnf install -y python3-tkinter espeak-ng python3-pip python3-devel development-tools alsa-lib-devel libsndfile
python3 -m pip install --upgrade pip --break-system-packages || python3 -m pip install --upgrade pip
python3 -m pip install numpy soundfile sounddevice requests --break-system-packages || python3 -m pip install numpy soundfile sounddevice requests
```
for Arch-based:
``` bash
#!/bin/bash
set -e
sudo pacman -Syu --noconfirm
sudo pacman -S --noconfirm --needed tk espeak-ng python-pip alsa-lib libsndfile base-devel
python3 -m pip install --upgrade pip --break-system-packages || python3 -m pip install --upgrade pip
python3 -m pip install numpy soundfile sounddevice requests --break-system-packages || python3 -m pip install numpy soundfile sounddevice requests
```
