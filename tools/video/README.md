# Demo video (docs/auctiondeposit-demo.mp4)

91 s (v3, `docs/auctiondeposit-demo-v3.mp4`), 1920x1080, 30 fps, narrated, made in code. Every name and auction is fictional.

1. Narration (Kokoro-82M, voice af_heart): `pip install kokoro-onnx soundfile`, download
   `kokoro-v1.0.fp16.onnx` and `voices-v1.0.bin` from github.com/thewh1teagle/kokoro-onnx releases
   (model-files-v1.0) into `$KOKORO_DIR`, then `python3 voice.py` (writes voice/*.wav and durations.json).
2. Photo: George E. Koronaios, "The Acropolis of Athens at dusk on September 6, 2022", CC BY-SA 4.0,
   Wikimedia Commons. Take the 3840 px rendition, `ffmpeg -i in.jpg -vf "crop=3840:2160:0:200,scale=2304:1296" photo/acropolis.jpg`.
3. `python3 make_scenes.py` (seven HTML scenes, lengths fitted to the narration), `python3 render.py stills s1:4 ...`
   to check frames, `python3 render.py video` (one mp4 per scene via Playwright + ffmpeg).
4. Join with the concat demuxer (`-c copy`), build the narration track (each line 0.6 s into its scene),
   mux with `-c:v copy -c:a aac -af loudnorm=I=-16:TP=-1.5`.
