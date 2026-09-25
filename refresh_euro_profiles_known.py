import asyncio
import aiohttp
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = 'https://fantaking-api.dunkest.com/api/v1'
HEADERS = {
    'origin': 'https://euroleaguefantasy.euroleaguebasketball.net',
    'referer': 'https://euroleaguefantasy.euroleaguebasketball.net/',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
    'accept': 'application/json',
}
CONC = 25

async def fetch(session, pid, sem):
    url = f'{BASE}/players/{pid}/profile?league=10'
    async with sem:
        for attempt in range(3):
            try:
                async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(2 + attempt * 3)
                        continue
                    if resp.status != 200:
                        return None
                    data = (await resp.json(content_type=None)).get('data')
                    if data and data.get('team') and data.get('position') and (data.get('quotation') or 0) > 0:
                        return data
                    return None
            except Exception:
                if attempt == 2:
                    return None
                await asyncio.sleep(0.5 + attempt)
    return None

async def main():
    path = ROOT / 'fantasy_profiles_active.json'
    if not path.exists():
        raise SystemExit('Missing fantasy_profiles_active.json seed file')
    old = json.loads(path.read_text(encoding='utf-8'))
    ids = sorted({int(p['id']) for p in old if p.get('id')})
    sem = asyncio.Semaphore(CONC)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=CONC)) as session:
        out = []
        for i in range(0, len(ids), 300):
            batch = ids[i:i+300]
            res = await asyncio.gather(*[fetch(session, pid, sem) for pid in batch])
            out.extend([r for r in res if r])
            print(f'refreshed {min(i+300, len(ids))}/{len(ids)} active {len(out)}', flush=True)
    if len(out) < max(100, len(old) * 0.70):
        raise SystemExit(f'Too few active profiles fetched: {len(out)} from previous {len(old)}')
    out.sort(key=lambda x: x['id'])
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote', path, 'players', len(out))

if __name__ == '__main__':
    asyncio.run(main())
