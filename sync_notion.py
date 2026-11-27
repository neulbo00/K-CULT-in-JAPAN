import json, os, subprocess, sys, urllib.request
from datetime import date, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ENV=ROOT/".env"
DB="efd10c5f-8d59-4491-b3a7-ff2d177c269e"
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
    if t=="multi_select": return ", ".join(x.get("name","") for x in p.get(t,[]))
    return ""
def post(url,token,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+token,"Notion-Version":"2025-09-03","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=45) as r: return json.loads(r.read())
    except Exception as e: raise RuntimeError("Notion API request failed: "+str(e))
def fetch(token):
    urls=["https://api.notion.com/v1/data_sources/"+DB+"/query","https://api.notion.com/v1/databases/"+DB+"/query"]
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
def git(*args):
    p=subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True)
    if p.returncode: raise RuntimeError("git "+ " ".join(args)+" failed: "+p.stderr.strip())
    return p.stdout.strip()
def main():
    load_env()
    token=next((os.getenv(k) for k in ("NOTION_API_KEY","NOTION_TOKEN","NOTION_API_TOKEN") if os.getenv(k)),None)
    if not token: raise RuntimeError(".env에 NOTION_API_KEY 또는 NOTION_TOKEN이 필요합니다.")
    pages=fetch(token); events=[]
    for page in pages:
        if page.get("archived") or page.get("in_trash"): continue
        p=page.get("properties",{}); v={k:value(p.get(n,{})) for k,n in FIELDS.items()}
        d=v["date"] if isinstance(v["date"],dict) else {}
        item={"name":str(v["name"] or "").strip(),"type":str(v["type"] or "").strip(),"start":(d.get("start") or "")[:10],"end":(d.get("end") or "")[:10],"category":str(v["category"] or "").strip(),"promoter":str(v["promoter"] or "").strip(),"source":str(v["source"] or "").strip(),"artist":str(v["artist"] or "").strip()}
        if item["name"]:
            if item["start"]: date.fromisoformat(item["start"])
            if item["end"]: date.fromisoformat(item["end"])
            events.append(item)
    minimum=int(os.getenv("SYNC_MIN_RECORDS","250"))
    if len(events)<minimum: raise RuntimeError("Safety stop: "+str(len(events))+" records; minimum "+str(minimum))
    events.sort(key=lambda x:(x["start"] or "9999-99-99",x["name"]))
    output="window.KDATA="+json.dumps({"generatedAt":datetime.now().astimezone().date().isoformat(),"total":len(events),"events":events},ensure_ascii=False,separators=(",",":"))+";\n"
    target=ROOT/"data.js"
    if target.read_text(encoding="utf-8")==output: print("No changes; skip GitHub update."); return
    target.write_text(output,encoding="utf-8",newline="\n")
    if git("branch","--show-current")!="main": raise RuntimeError("Safety stop: current branch must be main.")
    git("add","--","data.js")
    if not git("status","--porcelain","--","data.js"): print("No staged changes."); return
    git("commit","-m","data: sync Notion events "+datetime.now().date().isoformat())
    git("push","origin","main")
    print("Synced",len(events),"events. GitHub Pages deployment will follow.")
if __name__=="__main__":
    try: main()
    except Exception as e: print("SYNC ERROR:",e,file=sys.stderr); sys.exit(1)
