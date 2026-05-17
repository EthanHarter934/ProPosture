import ctypes

mci = ctypes.windll.winmm.mciSendStringW
path = r'C:\Users\ethar\AppData\Local\ProPosture\tts_cache\4a0d02874652cc1cc8a48bff822605532232f18fda57bcb56c32b75d1d6632ac.mp3'

res = mci(f'open "{path}" alias media', None, 0, 0)
print('open:', res)

res = mci('play media wait', None, 0, 0)
print('play:', res)

mci('close media', None, 0, 0)
