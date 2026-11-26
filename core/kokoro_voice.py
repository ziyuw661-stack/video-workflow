"""Optional local Kokoro voice; timing from generated PCM, not word counts."""
import re
import wave


def make_audio(scenes, folder, voice, lang_code, speed=1.0):
    from kokoro import KPipeline
    import numpy as np
    if not voice or not lang_code or not .6 <= speed <= 1.6:
        raise ValueError("Confirm Kokoro language, voice and speed first")
    pipeline = KPipeline(lang_code=lang_code)
    folder.mkdir(exist_ok=True)
    for i, scene in enumerate(scenes,1):
        if scene.get("audio"):
            continue
        wav = folder / f"kokoro-{i:03}.wav"
        cues, position = [], 0
        with wave.open(str(wav), "wb") as out:
            out.setparams((1,2,24000,0,"NONE","not compressed"))
            for sentence in re.split(r"(?<=[。！？])|(?<=[.!?])\s+", scene["narration"].strip()):
                sentence = sentence.strip()
                if not sentence:
                    continue
                start = position
                for _, _, samples in pipeline(sentence, voice=voice, speed=speed):
                    if samples is None:
                        continue
                    samples = np.asarray(samples)
                    if samples.ndim != 1 or not np.isfinite(samples).all():
                        raise ValueError("Kokoro returned invalid PCM")
                    out.writeframes(np.asarray(np.clip(samples,-1,1)*32767,dtype="<i2").tobytes())
                    position += len(samples)
                if position == start:
                    raise ValueError("Kokoro returned no speech for a sentence")
                cues.append([start/24000, position/24000, sentence])
        if not cues:
            raise ValueError("No real Kokoro speech cues")
        scene.update(audio=str(wav.resolve()),cues=cues)
