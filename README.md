# israel-bank-branches · סניפי בנקים בישראל

[![PyPI](https://img.shields.io/pypi/v/israel-bank-branches?color=2447D6)](https://pypi.org/project/israel-bank-branches/)
[![tests](https://github.com/aiterra-il/israel-bank-branches-python/actions/workflows/tests.yml/badge.svg)](https://github.com/aiterra-il/israel-bank-branches-python/actions/workflows/tests.yml)
[![license](https://img.shields.io/badge/license-MIT-3E96F9)](LICENSE)
![dependencies](https://img.shields.io/badge/dependencies-0-060B22)

Every bank branch in Israel, straight from the open data of the **Bank of Israel** on data.gov.il, for Python: address, phone, accessibility, the day it is closed, location, branches that closed and where they were merged, and the SWIFT codes of the banks. No API key.

This is the Python edition of the [israel-bank-branches](https://www.npmjs.com/package/israel-bank-branches) package on npm. The tests compare the record cleanup, lookup, search and distance functions with the answers of the JavaScript version on the full list of branches.

- **Payment and refund forms.** The customer types a bank and branch number, and you show the branch name and address and catch a mistake before the transfer fails.
- **Invoicing and payroll.** Check that the branch exists and has not closed.
- **Apps.** The branches nearest to the user, with a Google Maps link.

## Install

```bash
pip install israel-bank-branches
```

No dependencies. Python 3.10 or newer. Type hints included.

## Use

```python
from israel_bank_branches import get_branch, load_banks, load_branches, nearest_branches, search_branches

branch = get_branch(12, 532)
branch["bank_name"], branch["name"], branch["address"], branch["city"], branch["closed_day"]
# ('בנק הפועלים', 'שאול המלך', 'דניאל פריש 3', 'תל אביב -יפו', 'שישי')

branches = load_branches()

[(item["name"], item["address"]) for item in search_branches(branches, "בת ים", bank_code=10)]
# [('מרכז שירות בת-ים', 'שדרות העצמאות 67'), ('עסקים בת-ים', 'בלפור 80'), ('בת ים', 'בלפור 80')]

[(item["name"], item["distance_km"]) for item in nearest_branches(branches, 32.0167, 34.75, limit=2)]
# [('בת ים', 0.4), ('פועלים Business בת ים', 0.4)]

banks = load_banks()
next(bank for bank in banks if bank["code"] == 12)["swift"]
# 'POALILITXXX'
```

`get_branch()` downloads the whole list once and keeps it in memory, so the next lookup does not go to the network. To refresh: `get_branch(12, 532, refresh=True)`.

The package ships no data file. Each `load_branches()` call reads the current list from data.gov.il, as the npm package does. A snapshot of the same list is published as a dataset: [aiterra/israel-bank-branches on Hugging Face](https://huggingface.co/datasets/aiterra/israel-bank-branches).

### Errors

When data.gov.il is not available, `BranchLookupError` is raised with `code` set to one of `network`, `timeout`, `blocked`, `server`, `format`.

## API

| Function | What it does |
|---|---|
| `get_branch(bank_code, branch_code)` | A branch by bank code and branch number, or `None` |
| `load_branches()` | All branches, including closed ones |
| `search_branches(branches, text, *, bank_code, include_closed, limit)` | Search by city, branch name or street |
| `nearest_branches(branches, lat, lng, *, bank_code, limit)` | The nearest open branches, with the distance in km |
| `find_branch(branches, bank_code, branch_code)` | Like `get_branch`, on a list you already loaded |
| `load_banks()` | The banks: name, website, SWIFT, address and phone |
| `map_url(branch)` | A Google Maps link to the branch |
| `to_branch(record)`, `to_bank(record)` | Turn a raw data.gov.il record into a clean dict |

Every function takes `timeout=` in seconds where it goes to the network (15 by default).

## Source of the data

[The bank branches database of the Bank of Israel](https://data.gov.il/he/datasets/bank_israel/branches) on data.gov.il, used under the [data.gov.il terms of use](https://data.gov.il/terms-of-use). This is a community library with no official connection to the Bank of Israel. Check the details with the bank before a large transfer.

<div dir="rtl">

## בעברית

כל סניפי הבנקים בישראל, ישר מהמאגר הפתוח של **בנק ישראל** ב-data.gov.il, לפייתון: כתובת, טלפון, נגישות, יום סגירה, מיקום על המפה, סניפים שנסגרו ולאן הם מוזגו, וקודי SWIFT של הבנקים. אין צורך במפתח API.

- **טפסי תשלום והחזרים.** הלקוח מקליד בנק ומספר סניף, ומיד רואים שם הסניף וכתובת.
- **חשבוניות ומערכות שכר.** מוודאים שהסניף קיים ושלא נסגר.
- **אפליקציות.** הסניף הקרוב למשתמש לפי מיקום, עם קישור לגוגל מפות.

לנסות בלי קוד: **[חיפוש סניף בנק לפי מספר או עיר](https://www.aiterra.co.il/tools/bank-branch-lookup)** באתר של Aiterra.

</div>

## Licence

MIT for the code. The data belongs to the State of Israel and is used under the data.gov.il terms of use, which ask to name the source. Built by [Aiterra](https://www.aiterra.co.il), a software studio in Israel that builds AI agents, voice agents and websites.
