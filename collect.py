"""Collect public YouTube search metadata for AI-selected keywords, not media."""
import argparse,csv,datetime,json,shutil,subprocess,sys
from pathlib import Path
def main():
    p=argparse.ArgumentParser()
    p.add_argument("profile",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--limit",type=int,default=8)
    a=p.parse_args()
    cfg=json.loads(a.profile.read_text(encoding="utf-8"))
    words=cfg.get("keywords",[])
    if not words or not 1<=a.limit<=30: p.error("AI must populate keywords; limit 1-30")
    fields=["collected_date","direction","platform","keyword","title","channel","views","published_date","url"]
    rows={}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():
        with a.output.open(encoding="utf-8-sig",newline="") as f:
            for row in csv.DictReader(f): rows[row["url"]]=row
    failures=[]; successes=0
    for word in words:
        result=subprocess.run([sys.executable,"-m","yt_dlp","--flat-playlist","--dump-single-json","--skip-download",
                               f"ytsearch{a.limit}:{word}"],capture_output=True,text=True,encoding="utf-8")
        if result.returncode:
            failures.append({"keyword":word,"error":result.stderr[-800:]})
            continue
        successes+=1
        for e in json.loads(result.stdout).get("entries",[]):
            if not e or not e.get("id"): continue
            url="https://www.youtube.com/watch?v="+e["id"]
            rows[url]=dict(zip(fields,[str(datetime.date.today()),cfg.get("direction",""),"YouTube",word,
                e.get("title",""),e.get("channel") or e.get("uploader",""),e.get("view_count") if e.get("view_count") is not None else "unknown",
                e.get("upload_date") or "unknown",url]))
    if not successes: raise SystemExit("All searches failed: "+str(failures))
    temp=a.output.with_suffix(".tmp")
    with temp.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows(sorted(rows.values(),key=lambda x:(x["collected_date"],int(x["views"]) if str(x["views"]).isdigit() else -1),reverse=True))
    temp.replace(a.output)
    print(json.dumps({"rows":len(rows),"failed_keywords":failures,"output":str(a.output)},ensure_ascii=False))
if __name__=="__main__":main()
