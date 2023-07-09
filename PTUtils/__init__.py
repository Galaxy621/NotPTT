from __future__ import annotations

import hashlib
import random
import string
import time

import PTServer

VALID_NAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-!@#$%^&*()+=[]{}~ "
BAD_WORDS = ["fart"]

def sha256(str: str):
    return hashlib.sha256(str.encode()).hexdigest()

def keygen_alphanumeric(len: int):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(len))

def anticheat(sprite: str):
    if not sprite.startswith("spr_player") and not sprite.startswith("spr_knight") and not sprite.startswith("spr_shotgun") and not sprite.startswith("spr_ratmount") and not sprite.startswith("spr_lone") and sprite != "spr_noise_vulnerable2" and sprite != "spr_noise_crusherfall":
        sprite = "spr_player_idle"

    return sprite

def clean(msg: str, length: int = 256, bad_words: list[str] = BAD_WORDS):
    msg = msg.strip()
    msg = ''.join(c for c in msg if c in VALID_NAME_CHARS)

    if len(msg) > length and length > 0:
        msg = msg[:length]

    for word in bad_words:
        msg = msg.replace(word, "*"*len(word))

    return msg

def clean_name(name: str, bad_words: list[str] = BAD_WORDS):
    name = clean(name, 16, bad_words=bad_words)
    name = name.replace(" ", "-")

    if name == "":
        name = "Player"

    return name

def generate_unique_id(users: dict[int, PTServer.Client], digits: int = 4):
    id = random.randint(0, 10 ** digits)

    while id in users:
        id = random.randint(0, 10 ** digits)

    return id


class Ticker:
    def __init__(self, interval: float):
        self.Interval = interval
        self.LastTick = 0

    # Either return true, or sleep until the next tick
    def tick(self):
        timeSinceLastTick = time.time() - self.LastTick

        if timeSinceLastTick > self.Interval:
            self.LastTick = time.time()
        else:
            time.sleep(self.Interval - timeSinceLastTick)
        
        return True