"""Explicit YouTube OAuth, private upload and approved scheduling, never called by production tick."""
import datetime as dt
import json
import os
from pathlib import Path

SCOPE = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def settings(a):
    p = a.p.get("publication", {})
    if not p.get("youtube_enabled") or not p.get("youtube_channel_id"):
        raise ValueError("Enable YouTube explicitly and set the expected channel ID")
    return p


def channel(service, configured):
    result = service.channels().list(part="id", mine=True).execute().get("items", [])
    if len(result) != 1 or result[0]["id"] != configured:
        raise ValueError("OAuth account does not match configured YouTube channel")


def service(creds):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def authorize(a, client):
    from google_auth_oauthlib.flow import InstalledAppFlow
    configured = settings(a)["youtube_channel_id"]
    credentials = InstalledAppFlow.from_client_secrets_file(str(client), SCOPE).run_local_server(
        host="localhost", port=0, access_type="offline", prompt="consent")
    channel(service(credentials), configured)
    if not credentials.refresh_token:
        raise ValueError("OAuth refresh token missing; complete consent again")
    path = a.state / "youtube-oauth.json"
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(credentials.to_json())
    return {"authorized_channel": configured}


def future_time(value, now=None):
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t <= (now or dt.datetime.now(dt.timezone.utc)):
        raise ValueError("Scheduling requires a future ISO 8601 timestamp with offset")
    return t.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def publish(a, folder, job, private, when):
    from google.oauth2.credentials import Credentials
    from googleapiclient.http import MediaFileUpload
    from workflow import DIRS, digest, read, write
    configured = settings(a)
    if not (private or when):
        raise ValueError("Specify --private for the first upload, or --at for an uploaded private video")
    deadline = future_time(when) if when else None
    if deadline and not configured.get("allow_scheduling"):
        raise ValueError("YouTube scheduling has not been explicitly enabled")
    oauth = Credentials.from_authorized_user_file(str(a.state/"youtube-oauth.json"), SCOPE)
    yt = service(oauth)
    channel(yt, configured["youtube_channel_id"])
    path = a.state/(job+".publish.json")
    identity = digest(folder/"final.mp4")
    record = read(path) if path.exists() else None
    if record and (record.get("mode") != "youtube" or record.get("hash") != identity
                   or record.get("channel") != configured["youtube_channel_id"]):
        raise ValueError("Existing publication is for a different platform, channel or version")
    if record and not record.get("remote_id"):
        raise ValueError("Upload status unresolved. Verify the target Studio before any manual recovery; no duplicate retry.")
    if deadline and not record:
        raise ValueError("Use --private and verify processing before requesting scheduling")
    if not record:
        meta = read(folder/"publish.json")
        if type(configured.get("made_for_kids")) is not bool:
            raise ValueError("Explicitly configure the made_for_kids disclosure")
        snippet = {"title":meta["title"], "description":meta.get("description",""),
                   "tags":meta.get("tags",[]), "categoryId":str(configured.get("category_id","22"))}
        body = {"snippet":snippet,"status":{"privacyStatus":"private",
                "selfDeclaredMadeForKids":configured["made_for_kids"]}}
        if "contains_synthetic_media" in configured:
            if type(configured["contains_synthetic_media"]) is not bool:
                raise ValueError("Invalid synthetic media disclosure")
            body["status"]["containsSyntheticMedia"] = configured["contains_synthetic_media"]
        record = {"account_id":a.id, "job":job, "channel":configured["youtube_channel_id"],
                  "mode":"youtube", "hash":identity,"status":"upload_started"}
        write(path, record)
        request = yt.videos().insert(part="snippet,status", body=body,
            media_body=MediaFileUpload(str(folder/"final.mp4"), mimetype="video/mp4", resumable=True))
        response = None
        while response is None:
            _, response = request.next_chunk(num_retries=0)
        remote = response["id"]
        record.update(remote_id=remote, url="https://www.youtube.com/watch?v="+remote, status="uploaded_private_unverified")
        write(path, record)
    remote = record["remote_id"]
    videos = yt.videos().list(part="snippet,status,processingDetails", id=remote).execute()["items"]
    if len(videos) != 1 or videos[0]["snippet"]["channelId"] != record["channel"]:
        raise ValueError("Uploaded video not found on configured channel")
    item = videos[0]
    status = item["status"]
    processing = item.get("processingDetails",{}).get("processingStatus")
    if deadline:
        if status.get("publishAt"):
            if future_time(status["publishAt"]) != deadline:
                raise ValueError("Video already has a different remote schedule")
        else:
            if status["privacyStatus"] != "private" or processing != "succeeded" or record.get("ever_public"):
                raise ValueError("Only a processed private video that has never been public can be scheduled")
            # Re-check the deadline immediately before the write.
            future_time(deadline)
            update = {"privacyStatus":"private", "publishAt":deadline}
            for key in ("embeddable","license","publicStatsViewable","selfDeclaredMadeForKids","containsSyntheticMedia"):
                if key in status:
                    update[key] = status[key]
            verified = yt.videos().update(part="status", body={"id":remote,"status":update}).execute()["status"]
            if not verified.get("publishAt") or future_time(verified["publishAt"]) != deadline:
                raise ValueError("YouTube did not verify the requested schedule")
        record.update(status="scheduled", publish_at=deadline, processing=processing)
    else:
        if status["privacyStatus"] == "public":
            record.update(ever_public=True,status="public")
        elif status.get("publishAt"):
            record.update(status="scheduled",publish_at=status["publishAt"])
        else:
            record.update(status=status["privacyStatus"], processing=processing)
    remote_stats = yt.videos().list(part="statistics",id=remote).execute().get("items", [])
    if remote_stats:
        stats=remote_stats[0].get("statistics",{})
        record["statistics"] = {key:int(stats[key]) if key in stats else None for key in ("viewCount","likeCount","commentCount")}
    write(path, record)
    write(a.home/DIRS[6]/(job+".json"), record)
    return record
