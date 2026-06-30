# sound_manager.py
import os
import threading
# Note: You need to install pygame first: pip install pygame
import pygame


class SoundManager:
    def __init__(self):
        pygame.mixer.init(frequency=44100)
        # Assume your audio files are placed in the sounds folder
        self.sounds = {
            "granted": "/Users/yaohao/Desktop/PPE/PPE New/access_granted.mp3",
            "denied": "/Users/yaohao/Desktop/PPE/PPE New/access_denied.mp3",
            "alert": "/Users/yaohao/Desktop/PPE/PPE New/emergency_alert.mp3",
        }

    def _play(self, sound_name):
        """Internal playback function, using threads to prevent blocking the main program"""
        sound_path = self.sounds.get(sound_name)
        if sound_path and os.path.exists(sound_path):
            sound = pygame.mixer.Sound(sound_path)
            sound.play()
        else:
            print(f"⚠️ Warning: Audio file not found -> {sound_path}")

    def play_granted(self):
        threading.Thread(target=self._play, args=("granted",)).start()

    def play_denied(self):
        threading.Thread(target=self._play, args=("denied",)).start()

    def play_alert(self):
        threading.Thread(target=self._play, args=("alert",)).start()
