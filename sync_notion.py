import json, os, subprocess, sys, urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ENV=ROOT/".env"
DB="efd10c5f-8d59-4491-b3a7-ff2d177c269e"
SCHEDULE_DB="4883289c-aa60-4f6b-a57d-ad480820f7e0"
FIELDS={"name":"이벤트명","type":"이벤트 유형","date":"공연 날짜","category":"한류 카테고리","promoter":"프로모터","source":"공식 출처","artist":"관련 아티스트"}

def load_env():
    if not ENV.exists(): raise RuntimeError(".env 파일이 없습니다.")
    for line in ENV.read_text(encoding="utf-8-sig").splitlines():
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))

def value(p):
    t=p.get("type","")
    if t in ("title","rich_text"): return "".join(x.get("plain_text","") for x in p.get(t,[]))
    if t in ("select","status"): return (p.get(t) or {}).get("name","")
    if t=="url": return p.get("url") or ""
    if t=="date": return p.get("date") or {}
    if t=="checkbox": return bool(p.get("checkbox"))
    if t=="formula":
        f=p.get("formula") or {}
        return f.get(f.get("type"))
    if t=="relation": return [x.get("id","") for x in p.get("relation",[])]
    if t=="multi_select": return ", ".join(x.get("name","") for x in p.get(t,[]))
    return ""

def post(url,token,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+token,"Notion-Version":"2025-09-03","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=45) as r: return json.loads(r.read())
    except Exception as e: raise RuntimeError("Notion API request failed: "+str(e))

def fetch(token,db):
    urls=["https://api.notion.com/v1/data_sources/"+db+"/query","https://api.notion.com/v1/databases/"+db+"/query"]
    url=urls[0]; rows=[]; cursor=None
    while True:
        body={"page_size":100}
        if cursor: body["start_cursor"]=cursor
        try: result=post(url,token,body)
        except RuntimeError:
            if url!=urls[0]: raise
            url=urls[1]; result=post(url,token,body)
        rows.extend(result.get("results",[]))
        if not result.get("has_more"): return rows
        cursor=result.get("next_cursor")
        if not cursor: raise RuntimeError("Notion pagination cursor missing")

def notion_url(page_id):
    return "https://www.notion.so/"+page_id.replace("-","") if page_id else ""

def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True)
    if p.returncode: raise RuntimeError("git "+" ".join(args)+" failed: "+p.stderr.strip())
    return p.stdout.strip()

def read_payload(path,prefix):
    target=ROOT/path
    if not target.exists(): return None
    try: return json.loads(target.read_text(encoding="utf-8").split("=",1)[1].rsplit(";",1)[0])
    except Exception: return None

def main():
    load_env()
    token=next((os.getenv(k) for k in ("NOTION_API_KEY","NOTION_TOKEN","NOTION_API_TOKEN") if os.getenv(k)),None)
    if not token: raise RuntimeError(".env에 NOTION_API_KEY 또는 NOTION_TOKEN이 필요합니다.")

    generated=datetime.now().astimezone().date().isoformat()
    events=[]
    for page in fetch(token,DB):
        if page.get("archived") or page.get("in_trash"): continue
        p=page.get("properties",{}); v={k:value(p.get(n,{})) for k,n in FIELDS.items()}
        d=v["date"] if isinstance(v["date"],dict) else {}
        item={"name":str(v["name"] or "").strip(),"type":str(v["type"] or "").strip(),"start":(d.get("start") or "")[:10],"end":(d.get("end") or "")[:10],"category":str(v["category"] or "").strip(),"promoter":str(v["promoter"] or "").strip(),"source":str(v["source"] or "").strip(),"artist":str(v["artist"] or "").strip()}
        if item["name"]:
            if item["start"]: date.fromisoformat(item["start"])
            if item["end"]: date.fromisoformat(item["end"])
            events.append(item)
    minimum=int(os.getenv("SYNC_MIN_RECORDS","250"))
    if len(events)<minimum: raise RuntimeError("Safety stop: "+str(len(events))+" event records; minimum "+str(minimum))
    events.sort(key=lambda x:(x["start"] or "9999-99-99",x["name"]))
    event_payload={"generatedAt":generated,"total":len(events),"events":events}
    event_output="window.KDATA="+json.dumps(event_payload,ensure_ascii=False,separators=(",",":"))+";\\n"

    schedules=[]
    for page in fetch(token,SCHEDULE_DB):
        if page.get("archived") or page.get("in_trash"): continue
        p=page.get("properties",{})
        def prop(name): return value(p.get(name,{}))
        # Match the public Notion view: expose only rows whose formula checkbox is true.
        if prop("노출대상") is not True: continue
        d=prop("공연일"); d=d if isinstance(d,dict) else {}
        relations=prop("이벤트"); relations=relations if isinstance(relations,list) else []
        item={
            "name":str(prop("일정명") or "").strip(),
            "eventName":str(prop("원문 이벤트명") or "").strip(),
            "venue":str(prop("공연장") or "").strip(),
            "date":(d.get("start") or "")[:10],
            "dateEnd":(d.get("end") or "")[:10],
            "time":str(prop("공연 시작시간") or "").strip(),
            "region":str(prop("지역") or "").strip(),
            "category":str(prop("한류 카테고리") or "").strip(),
            "status":str(prop("공연 상태") or "").strip(),
            "certainty":str(prop("일정 확정도") or "").strip(),
            "connection":str(prop("이벤트 연결상태") or "").strip(),
            "source":str(prop("일정 출처") or "").strip(),
            "pageUrl":page.get("url") or notion_url(page.get("id","")),
            "eventUrl":notion_url(relations[0]) if relations else ""
        }
        if item["name"] and item["date"]:
            date.fromisoformat(item["date"])
            if item["dateEnd"]: date.fromisoformat(item["dateEnd"])
            schedules.append(item)
    min_schedules=int(os.getenv("SYNC_MIN_SCHEDULES","400"))
    if len(schedules)<min_schedules:
        raise RuntimeError("Safety stop: "+str(len(schedules))+" public schedule records; minimum "+str(min_schedules))
    schedules.sort(key=lambda x:(x["date"],x["time"],x["name"]))
    schedule_payload={"generatedAt":generated,"source":"Notion 일본 한류 공연 일정 / 노출대상=true","total":len(schedules),"schedules":schedules}
    schedule_output="window.KSCHEDULES="+json.dumps(schedule_payload,ensure_ascii=False,separators=(",",":"))+";\\n"

    event_old=read_payload("data.js","window.KDATA")
    schedule_old=read_payload("schedule_data.js","window.KSCHEDULES")
    event_changed=not event_old or event_old.get("events")!=events
    schedule_changed=not schedule_old or schedule_old.get("schedules")!=schedules
    if not event_changed and not schedule_changed:
        print("No event or schedule changes; GitHub update skipped."); return

    if git("branch","--show-current")!="main":
        raise RuntimeError("Safety stop: current branch must be main.")
    if event_changed: (ROOT/"data.js").write_text(event_output,encoding="utf-8",newline="\\n")
    if schedule_changed: (ROOT/"schedule_data.js").write_text(schedule_output,encoding="utf-8",newline="\\n")
    paths=[]
    if event_changed: paths.append("data.js")
    if schedule_changed: paths.append("schedule_data.js")
    git("add","--",*paths)
    if not git("status","--porcelain","--",*paths):
        print("No staged changes."); return
    git("commit","-m","data: sync Notion events and schedules "+generated)
    git("push","origin","main")
    print("Synced",len(events),"events and",len(schedules),"public schedules. GitHub Pages deployment will follow.")

if __name__=="__main__":
    try: main()
    except Exception as e: print("SYNC ERROR:",e,file=sys.stderr); sys.exit(1)
