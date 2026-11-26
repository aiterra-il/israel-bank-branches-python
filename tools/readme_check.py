import sys

from israel_bank_branches import get_branch, load_banks, load_branches, map_url, nearest_branches, search_branches

sys.stdout.reconfigure(encoding="utf-8")

branch = get_branch(12, 532)
print({name: branch[name] for name in ("bank_name", "name", "address", "city", "phone", "closed_day", "opened_on")})
print(map_url(branch))
branches = load_branches()
print(len(branches), sum(1 for item in branches if item["closed_on"]))
print([(item["name"], item["address"]) for item in search_branches(branches, "בת ים", bank_code=10)])
print([(item["bank_name"], item["name"], item["distance_km"]) for item in nearest_branches(branches, 32.0167, 34.75, limit=3)])
banks = load_banks()
print(next(bank for bank in banks if bank["code"] == 12)["swift"])
