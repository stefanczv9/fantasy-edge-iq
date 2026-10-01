import asyncio, aiohttp, json
from pathlib import Path
BASE='https://fantaking-api.dunkest.com/api/v1'
HEADERS={
 'origin':'https://euroleaguefantasy.euroleaguebasketball.net',
 'referer':'https://euroleaguefantasy.euroleaguebasketball.net/',
 'user-agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
 'accept':'application/json'
}
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'data'/'fantasy_profiles_active.json'
profiles=json.load(open(PATH,encoding='utf-8'))
async def fetch(session,pid,sem):
    url=f'{BASE}/players/{pid}/profile?league=10'
    async with sem:
        for attempt in range(4):
            try:
                async with session.get(url,headers=HEADERS,timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    txt=await resp.text()
                    if resp.status==429:
                        await asyncio.sleep(2+attempt*2); continue
                    if resp.status!=200:
                        return None
                    js=json.loads(txt).get('data')
                    return js
            except Exception:
                if attempt==3: return None
                await asyncio.sleep(0.5+attempt)
async def main():
    sem=asyncio.Semaphore(25)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=25)) as session:
        res=await asyncio.gather(*[fetch(session,p['id'],sem) for p in profiles])
    byid={r['id']:r for r in res if r and r.get('team') and r.get('position')}
    updated=[]; missing=[]
    for old in profiles:
        new=byid.get(old['id'])
        if new:
            updated.append(new)
        else:
            updated.append(old); missing.append(old['id'])
    updated.sort(key=lambda x:x['id'])
    PATH.write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding='utf-8')
    print('updated profiles',len(updated),'fresh',len(byid),'missing',len(missing))
    for name in ['Lamar Stevens','Carlik Jones','Braxton Key']:
        for p in updated:
            nm=(p.get('first_name','')+' '+p.get('last_name','')).strip()
            if nm==name:
                print(name, 'quotation', p.get('quotation'), 'total_plus', p.get('total_plus'), 'popularity', p.get('popularity'))
asyncio.run(main())
