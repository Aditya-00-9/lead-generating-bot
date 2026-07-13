import json
import urllib.request

stats = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/stats", timeout=15).read())
leads = json.loads(
    urllib.request.urlopen("http://127.0.0.1:8000/api/leads?page=1&page_size=8", timeout=15).read()
)
print("Stats:", stats)
print(f"Total leads: {leads['total']}\nRecent:")
for x in leads["items"]:
    hook = (x.get("suggested_hook") or "")[:55]
    print(f"  [{x['intent_label']}] {x['competitor']} | {x['platform']} | rank={x['rank_score']:.2f}")
    print(f"    {x['source_url'][:70]}")
    if hook:
        print(f"    hook: {hook}...")
