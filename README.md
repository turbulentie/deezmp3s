```
      ██                                             ████
     ░██                                    ██████  █░░░ █
     ░██  █████   █████  ██████ ██████████ ░██░░░██░    ░█  ██████
  ██████ ██░░░██ ██░░░██░░░░██ ░░██░░██░░██░██  ░██   ███  ██░░░░
 ██░░░██░███████░███████   ██   ░██ ░██ ░██░██████   ░░░ █░░█████
░██  ░██░██░░░░ ░██░░░░   ██    ░██ ░██ ░██░██░░░   █   ░█ ░░░░░██
░░██████░░██████░░██████ ██████ ███ ░██ ░██░██     ░ ████  ██████
 ░░░░░░  ░░░░░░  ░░░░░░ ░░░░░░ ░░░  ░░  ░░ ░░       ░░░░  ░░░░░░
```

## STATUS
Originally coded by [UVU](https://gitlab.com/uvu). Archieved on Github for own usage.

## What is it
This is ripper and packer from deezer.

## Requirements
* arrow
* Click
* cryptography
* eyed3
* loguru
* mutagen
* requests
* Unidecode

## Installation
Fetch the repo from github
```
git clone https://github.com/turbulentie/deezmp3s
```
Create a virtual environment for your installations
```
python3 -m venv ~/.virtualenvs/deezmp3s
source ~/.virtualenvs/deezmp3s/bin/activate
```
You need install the python requirements
```
pip install -r requirements.txt
```

## How to run
* Edit settings.py, enter your ARL (login in browser, grab the arl cookie)
* `./deezmp3s <id>`
* Find the release on amazon/tidal, and use that URL in your nfo
* Profit !

## Notes
This package not maintained by me. Original code was available on [GitLab](https://gitlab.com/uvu/deezmp3s)
