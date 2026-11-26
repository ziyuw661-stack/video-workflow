#!/usr/bin/env python3
"""Render AI-authored narrated scenes to a complete MP4 and publication package."""
import argparse
import asyncio
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

def run(*args):
    subprocess.run([str(x) for x in args], check=True)

def probe(path):
    return json.loads(subprocess.check_output(
        ["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(path)], text=True))

def audio_duration(path):
    data = probe(path)
    if not any(s["codec_type"] == "audio" for s in data["streams"]):
        raise ValueError(f"No audio in {path}")
    duration = float(data["format"]["duration"])
    if duration <= 0:
        raise ValueError(f"Empty audio: {path}")
    return duration

def font(size, custom=None):
    candidates = [custom, os.environ.get("VIDEO_FONT"),
        "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in candidates:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise RuntimeError("No font found. Set VIDEO_FONT to a licensed font supporting your language.")

def lines(draw, text, f, width):
    result=[]
    for paragraph in str(text).splitlines():
        if not paragraph:
            continue
        current=""
        for ch in paragraph:
            if current and draw.textlength(current+ch,font=f)>width:
                if " " in current and not ch.isspace():
                    prefix, rest=current.rsplit(" ",1)
                    if prefix:
                        result.append(prefix)
                        current=rest+ch
                        continue
                result.append(current.rstrip())
                current=ch.lstrip()
            else:
                current+=ch
        if current.strip():
            result.append(current.strip())
    return result

def block(draw, text, x, y, max_width, max_height, size, color, custom):
    while size>=14:
        f=font(size,custom)
        ls=lines(draw,text,f,max_width)
        step=int(size*1.35)
        if len(ls)*step<=max_height and all(draw.textlength(s,font=f)<=max_width for s in ls):
            for s in ls:
                draw.text((x,y),s,font=f,fill=color,anchor="lt")
                y+=step
            return
        size-=2
    raise ValueError("Text does not fit; shorten scene heading/body or split scenes.")

def artwork(spec, scene, index, count, base, dest, cover=False):
    w,h=spec["width"],spec["height"]
    style=spec.get("style",{})
    bg=style.get("background","#142638"); fg=style.get("foreground","#FFFFFF")
    accent=style.get("accent","#69D6B5"); custom=style.get("font")
    if custom:
        custom=str((base/custom).resolve())
    im=Image.new("RGB",(w,h),bg)
    d=ImageDraw.Draw(im)
    margin=int(w*.07)
    d.rectangle((margin,margin,margin+int(w*.12),margin+max(5,int(h*.01))),fill=accent)
    portrait=h>w
    photo=scene.get("visual")
    if photo:
        source=(base/photo).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        # Reserve independent text area; never cover subtitles with an image.
        if portrait:
            box=(margin,int(h*.12),w-margin,int(h*.43))
            tx,ty,tw,th=margin,int(h*.47),w-2*margin,int(h*.24)
        else:
            box=(int(w*.56),int(h*.13),w-margin,int(h*.72))
            tx,ty,tw,th=margin,int(h*.20),int(w*.45),int(h*.49)
        x1,y1,x2,y2=box
        with Image.open(source) as photoim:
            im.paste(ImageOps.fit(photoim.convert("RGB"),(x2-x1,y2-y1)),(x1,y1))
    else:
        tx,ty,tw,th=margin,int(h*.23),w-2*margin,int(h*.48)
        # Editorial graphic motif, varied by section, not a factual chart.
        d.ellipse((int(w*.76),int(h*.09),int(w*.90),int(h*.09+w*.14)),outline=accent,width=max(2,w//250))
    heading=spec["title"] if cover else scene["heading"]
    block(d,heading,tx,ty,tw,int(th*.54),int(min(w,h)*.088),fg,custom)
    if not cover:
        block(d,scene.get("body",""),tx,ty+int(th*.57),tw,int(th*.43),int(min(w,h)*.047),accent,custom)
        d.text((margin,int(h*.77)),f"{index+1:02d} / {count:02d}",font=font(max(14,int(min(w,h)*.025)),custom),fill=fg)
        d.rectangle((margin,int(h*.82),w-margin,int(h*.827)),fill="#55606C")
        d.rectangle((margin,int(h*.82),margin+int((w-2*margin)*(index+1)/count),int(h*.827)),fill=accent)
    im.save(dest)

def stamp(sec):
    ms=round(sec*1000)
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"

def clean_spec(spec):
    for k in ("title","language","width","height","scenes"):
        if k not in spec:
            raise ValueError(f"Missing {k}")
    w,h=spec["width"],spec["height"]
    if not all(isinstance(x,int) and 480<=x<=2160 and x%2==0 for x in (w,h)):
        raise ValueError("Even dimensions required, 480-2160 px")
    if not isinstance(spec["scenes"],list) or not 1<=len(spec["scenes"])<=120:
        raise ValueError("1-120 scenes required")
    for scene in spec["scenes"]:
        for k in ("heading","narration"):
            if not isinstance(scene.get(k),str) or not scene[k].strip():
                raise ValueError(f"Each scene requires {k}")
    if not spec.get("voice") and any(not s.get("audio") for s in spec["scenes"]):
        raise ValueError("Choose a real TTS voice or supply audio for each scene.")

async def synth(text, voice, audio, subtitles):
    import edge_tts
    comm=edge_tts.Communicate(text,voice,boundary="SentenceBoundary")
    cues=[]
    with audio.open("wb") as f:
        async for chunk in comm.stream():
            if chunk["type"]=="audio":
                f.write(chunk["data"])
            elif chunk["type"]=="SentenceBoundary":
                start=chunk["offset"]/10_000_000
                end=start+chunk["duration"]/10_000_000
                cues.append((start,end,chunk["text"]))
    if audio.stat().st_size<1000 or not cues:
        raise RuntimeError("TTS returned no usable audio or sentence timing; use another voice or supply audio with timed cues.")
    return cues

def validate_cues(cues, duration, overlap_tolerance=0.0, corrections=None):
    """Normalize small provider boundary overlaps, never synthesize new timings.

    Tolerance is opt-in for provider metadata only. External and final
    timelines remain strict. Preserve the later cue's actual onset by
    trimming the preceding cue's end; reject reversed/empty intervals.
    """
    duration=float(duration)
    if not math.isfinite(duration) or duration<=0:
        raise ValueError("Invalid audio duration")
    valid=[]
    for index,(start,end,text) in enumerate(cues,1):
        start=float(start); end=float(end); text=str(text).strip()
        if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<=start or not text:
            raise ValueError(f"Invalid cue {index}: {start} -> {end}")
        if end>duration+max(overlap_tolerance,.001):
            raise ValueError(f"Cue {index} exceeds audio duration: {end} > {duration}")
        if end>duration:
            if corrections is not None:
                corrections.append({"cue":index,"kind":"audio_end_trim","seconds":round(end-duration,6)})
            end=duration
        if valid and start<valid[-1][1]:
            prev_start,prev_end,prev_text=valid[-1]
            overlap=prev_end-start
            if overlap>max(overlap_tolerance,1e-7)+1e-9 or start<=prev_start or start>=end:
                raise ValueError(f"Cue {index} overlaps previous cue by {overlap:.3f}s")
            valid[-1]=(prev_start,start,prev_text)
            if corrections is not None:
                corrections.append({"cue":index-1,"kind":"provider_overlap_trim","seconds":round(overlap,6)})
        if end<=start:
            raise ValueError(f"Cue {index} is empty after clipping")
        valid.append((start,end,text))
    if not valid:
        raise ValueError("No subtitle cues")
    return valid

def write_ass(path, cues, spec):
    w,h=spec["width"],spec["height"]
    size=max(22,int(min(w,h)*.048))
    def t(seconds):
        cs=round(seconds*100)
        return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"
    family=spec.get("subtitle_font","Arial")
    if any(c in family for c in ",\n\r"):
        raise ValueError("Invalid subtitle font family")
    header=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00101820,&H80101820,0,0,0,0,100,100,0,0,1,3,0,2,{int(w*.07)},{int(w*.07)},{int(h*.05)},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with path.open("w",encoding="utf-8") as f:
        f.write(header)
        for a,b,txt in cues:
            txt=txt.replace("\\","＼").replace("{","（").replace("}","）").replace("\n","\\N")
            f.write(f"Dialogue: 0,{t(a)},{t(b)},Default,,0,0,0,,{txt}\n")

def split_cues(cues,w,h,language):
    # Split long sentence cues into readable chunks; sentence bounds are real,
    # subdivisions are estimated and must be reviewed or replaced by word timings.
    result=[]
    limit=28 if language.startswith(("zh","ja","ko")) else (36 if h>w else 64)
    for a,b,txt in cues:
        if language.startswith(("zh","ja","ko")):
            parts=[txt[i:i+limit] for i in range(0,len(txt),limit)]
        else:
            parts=textwrap.wrap(txt,width=limit,break_long_words=False,break_on_hyphens=False)
        weights=[max(1,len(p)) for p in parts]
        total=sum(weights)
        offset=a
        for i,p in enumerate(parts):
            end=b if i==len(parts)-1 else offset+(b-a)*weights[i]/total
            result.append((offset,end,p))
            offset=end
    return result

async def render(specfile, output):
    base=specfile.resolve().parent
    spec=json.loads(specfile.read_text(encoding="utf-8"))
    clean_spec(spec)
    for exe in ("ffmpeg","ffprobe"):
        if not shutil.which(exe):
            raise RuntimeError(f"Install {exe} and add it to PATH")
    output=output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Output directory is not empty; choose a fresh path.")
    output.mkdir(parents=True,exist_ok=True)
    w,h=spec["width"],spec["height"]
    count=len(spec["scenes"])
    combined=[]; paths=[]; offset=0.0; timing_corrections=[]; timeline=[]
    (output/"audio").mkdir()
    artwork(spec,spec["scenes"][0],0,count,base,output/"cover.png",True)
    with tempfile.TemporaryDirectory(prefix="video_workflow_") as temp:
        work=Path(temp)
        for i,scene in enumerate(spec["scenes"]):
            print(f"Scene {i+1}/{count}",flush=True)
            audio=work/f"a{i:03}.mp3"
            if scene.get("audio"):
                audio=(base/scene["audio"]).resolve()
                if not scene.get("cues"):
                    raise ValueError("External audio requires real timed cues [start,end,text].")
                cues=scene["cues"]
            else:
                cues=await synth(scene["narration"],spec["voice"],audio,None)
            duration=audio_duration(audio)
            original=output/"audio"/f"scene-{i+1:03}{audio.suffix.lower()}"
            shutil.copyfile(audio,original)
            scene_corrections=[]
            cues=split_cues(validate_cues(cues,duration,
                overlap_tolerance=0.0 if scene.get("audio") else 0.10,
                corrections=scene_corrections),w,h,spec["language"])
            timing_corrections.extend(dict(item,scene=i+1) for item in scene_corrections)
            if scene_corrections:
                print(f"Scene {i+1}: normalized {len(scene_corrections)} small timing boundaries",flush=True)
            frames=math.ceil(duration*25)
            clip_duration=frames/25
            image=work/f"p{i:03}.png"
            artwork(spec,scene,i,count,base,image)
            shutil.copyfile(image,output/f"scene-{i+1:03}.png")
            clip=work/f"c{i:03}.mp4"
            # Subtle animated reveal without zooming text into unsafe areas.
            fade=min(.20,clip_duration/4)
            vf=f"fps=25,fade=t=in:st=0:d={fade:.3f},format=yuv420p"
            run("ffmpeg","-hide_banner","-loglevel","error","-y",
                "-loop","1","-framerate","25","-i",image,"-i",audio,
                "-map","0:v","-map","1:a","-vf",vf,"-af","apad",
                "-t",f"{clip_duration:.3f}","-c:v","libx264","-preset","fast","-crf","20",
                "-c:a","aac","-ar","48000","-ac","2",clip)
            actual=float(probe(clip)["format"]["duration"])
            combined.extend((offset+a,offset+b,t) for a,b,t in cues)
            timeline.append({"scene_id":scene.get("scene_id",i+1),"start":offset,"end":offset+actual, "audio":original.relative_to(output).as_posix(), "image":f"scene-{i+1:03}.png", "subtitles":[[offset+a,offset+b,t] for a,b,t in cues], "audio_duration":duration, "actions":[], "sfx":[], "transition":{"kind":"fade_in","seconds":fade}})
            offset+=actual
            paths.append(clip.name)
        (work/"concat.txt").write_text("".join(f"file '{p}'\n" for p in paths),encoding="utf-8")
        merged=work/"merged.mp4"
        run("ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",work/"concat.txt","-c","copy",merged)
        final_duration=float(probe(merged)["format"]["duration"])
        combined=validate_cues(combined,final_duration)
        srt=output/"final.srt"
        srt.write_text("\n\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{t}" for i,(a,b,t) in enumerate(combined,1))+"\n",encoding="utf-8")
        write_ass(work/"subs.ass",combined,spec)
        final=output/"final.mp4"
        # Relative ASS path avoids Windows drive-letter and quote escaping.
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i","merged.mp4",
                        "-vf","ass=subs.ass","-c:v","libx264","-preset","fast","-crf","20",
                        "-c:a","copy","-movflags","+faststart",str(final)],cwd=work,check=True)
    data=probe(final)
    streams={s["codec_type"]:s for s in data["streams"]}
    v=streams["video"]; a=streams["audio"]
    dur=float(data["format"]["duration"])
    avdiff=abs(float(v.get("duration",dur))-float(a.get("duration",dur)))
    if (v["width"],v["height"])!=(w,h) or avdiff>.15 or combined[-1][1]>dur+.001:
        raise RuntimeError("Technical gate failed: dimensions, A/V duration, or subtitle bounds")
    run("ffmpeg","-v","error","-xerror","-i",final,"-map","0:v","-map","0:a","-f","null","-")
    (output/"script.json").write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding="utf-8")
    (output/"publish.json").write_text(json.dumps({"title":spec["title"],"description":spec.get("description",""),
        "tags":spec.get("tags",[]),"sources":spec.get("sources",[]),"video":"final.mp4",
        "cover":"cover.png","status":"pending_human_review"},ensure_ascii=False,indent=2),encoding="utf-8")
    (output/"qc.json").write_text(json.dumps({"technical_checks":"passed","duration_seconds":dur,"av_difference_seconds":avdiff,
        "dimensions":[w,h],"subtitle_end_seconds":combined[-1][1],
        "visual_audio_content_review":"pending","timing_note":"sentence boundaries real; subdivisions estimated; review alignment",
        "timing_corrections":timing_corrections,
        "publication":"blocked_until_review"},indent=2),encoding="utf-8")
    (output/"timeline.json").write_text(json.dumps({"language":spec["language"],"width":w,"height":h,"fps":25,"scenes":timeline},ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Complete video: {final}")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("spec",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    try:
        asyncio.run(render(args.spec,args.output))
    except Exception as exc:
        print(f"Production failed: {exc}",file=sys.stderr)
        sys.exit(1)

if __name__=="__main__":
    main()
