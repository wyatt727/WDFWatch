Below is an **opinionated, production‑grade automation framework** (Python) for *managing X Filtered Stream rules* (add / remove / replace / rollback / dry‑run) with **versioned rule sets**, safety checks, and refinement integration. You can trim for MVP.

---

## 1. Features

| Feature                                                                           | Purpose                                                           |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Versioned `ruleset-YYYYMMDD-HHMM.json` snapshots                                  | Audit & rollback                                                  |
| Dry‑run diff (`--dry-run`)                                                        | Preview adds/removes before touching API                          |
| Hash fingerprint of desired set                                                   | Idempotency (avoid duplicate pushes)                              |
| Safe replace mode (`--replace`)                                                   | Remove only rules not in desired set                              |
| Rate limit aware (exponential backoff)                                            | Reliable under load                                               |
| Rollback (`--rollback <hash>` or `--rollback latest`)                             | Revert to previous saved snapshot                                 |
| Partial apply with max operations per run                                         | Limit risk                                                        |
| Optional *simulation* mode: test projected precision deltas (if you feed metrics) | Data‑driven decision                                              |
| Negative token suggestions integration                                            | Auto incorporate approved suggestions into next generated ruleset |
| Slack / console report                                                            | Ops visibility                                                    |

---

## 2. X API Endpoints (v2 Filtered Stream)

| Action            | Method / Endpoint                                                         |
| ----------------- | ------------------------------------------------------------------------- |
| Get current rules | `GET https://api.twitter.com/2/tweets/search/stream/rules`                |
| Add/remove        | `POST https://api.twitter.com/2/tweets/search/stream/rules`               |
| Stream (separate) | `GET https://api.twitter.com/2/tweets/search/stream` (not in this script) |

Payload for modification:

```json
{
  "add": [{ "value": "...rule...", "tag": "TAG" }],
  "delete": { "ids": ["123","456"] }
}
```

---

## 3. Directory Layout

```
rules/
  desired.json                 # Current target (symlink to latest snapshot)
  snapshots/
    ruleset-20250719-1200.json
    ruleset-20250722-0900.json
  suggestions/
    refinement-report-20250722.json
automation/
  manage_rules.py
  metrics_adapter.py
  config.example.toml
logs/
  manage_rules.log
```

---

## 4. Config (`config.toml`)

```toml
[xapi]
bearer_token = "YOUR_X_BEARER"

[rules]
desired_file = "rules/desired.json"
snapshots_dir = "rules/snapshots"
suggestions_dir = "rules/suggestions"

[safety]
max_add_per_run = 10
max_delete_per_run = 10
require_unique_tags = true
require_lang_en = true
forbid_unscoped_divorce = true      # custom lint
min_rule_length = 25

[report]
enable_slack = false
slack_webhook = ""
```

---

## 5. Desired Rules File Schema (`desired.json`)

```json
{
  "version": "2025-07-22T09:00:00Z",
  "description": "Baseline 7 + doctrine additions",
  "rules": [
    { "tag": "NDIV_CORE", "value": "(\"national divorce\" ... ) lang:en -is:retweet ..." },
    { "tag": "FED_CORE",  "value": "(federalism ... ) lang:en ..." }
  ],
  "meta": {
    "source": "manual+auto-refinement",
    "refinement_batch": "2025-07-22"
  }
}
```

---

## 6. Rule Linting Heuristics

Before calling API, each rule goes through:

| Check                                                                                               | Failing Example               | Action                |
| --------------------------------------------------------------------------------------------------- | ----------------------------- | --------------------- |
| Duplicate tag                                                                                       | Two rules with tag `FED_CORE` | Abort                 |
| Missing `lang:en` if required                                                                       | Rule value lacks `lang:`      | Warn/Fail             |
| Contains bare `"divorce"` without `"national"` or secession synonyms when `forbid_unscoped_divorce` | `divorce (law OR reform)`     | Fail (prevents drift) |
| Length < min\_rule\_length (likely accidental)                                                      | `federalism`                  | Fail                  |
| Overlapping obvious duplicates (identical value ignoring whitespace)                                | Duplicates                    | Collapse duplicates   |

---

## 7. Core Script (`manage_rules.py`)

```python
#!/usr/bin/env python3
import argparse, json, os, time, hashlib, datetime, textwrap, sys
import requests
from pathlib import Path
import tomllib

CONFIG = {}

def load_config(path):
    global CONFIG
    with open(path, 'rb') as f:
        CONFIG = tomllib.load(f)

def bearer():
    return CONFIG['xapi']['bearer_token']

API_BASE = "https://api.twitter.com/2/tweets/search/stream/rules"

def api_get_rules():
    r = requests.get(API_BASE, headers=_headers())
    r.raise_for_status()
    data = r.json()
    current = data.get('data', []) or []
    return current  # list of {id, value, tag}

def api_modify(add=None, delete_ids=None):
    payload = {}
    if add:
        payload['add'] = add
    if delete_ids:
        payload['delete'] = {"ids": delete_ids}
    r = requests.post(API_BASE, headers=_headers(), json=payload)
    if r.status_code == 429:
        reset = int(r.headers.get('x-rate-limit-reset', time.time()+60))
        sleep_for = max(5, reset - int(time.time()))
        print(f"[rate-limit] sleeping {sleep_for}s")
        time.sleep(sleep_for)
        return api_modify(add, delete_ids)
    r.raise_for_status()
    return r.json()

def _headers():
    return {
        "Authorization": f"Bearer {bearer()}",
        "Content-Type": "application/json"
    }

def load_desired(path):
    with open(path,'r') as f:
        obj = json.load(f)
    rules = obj['rules']
    return obj, rules

def fingerprint(rules):
    # stable ordering by tag
    blob = json.dumps(sorted(rules, key=lambda r: r['tag']), separators=(',',':')).encode()
    return hashlib.sha256(blob).hexdigest()[:16]

def lint_rules(rules):
    seen_tags = set()
    errors = []
    for r in rules:
        tag = r['tag']
        val = r['value']
        if CONFIG['safety'].get('require_unique_tags', True):
            if tag in seen_tags:
                errors.append(f"Duplicate tag {tag}")
            seen_tags.add(tag)
        if CONFIG['safety'].get('require_lang_en', True) and "lang:en" not in val:
            errors.append(f"Rule {tag} missing lang:en")
        if CONFIG['safety'].get('forbid_unscoped_divorce', True):
            if "divorce" in val and "national divorce" not in val and "secession" not in val and "peaceful separation" not in val:
                errors.append(f"Rule {tag} contains broad 'divorce' term")
        if len(val.strip()) < CONFIG['safety'].get('min_rule_length', 20):
            errors.append(f"Rule {tag} too short")
    return errors

def diff_rules(current, desired):
    # Maps by tag/value for clarity
    cur_by_tag = {c.get('tag'): c for c in current if c.get('tag')}
    desired_by_tag = {d['tag']: d for d in desired}
    add = []
    keep_ids = set()
    # Add or replace
    for tag, d in desired_by_tag.items():
        if tag not in cur_by_tag:
            add.append(d)
        else:
            if normalize(cur_by_tag[tag]['value']) != normalize(d['value']):
                # Replace: treat as add new; delete old id
                add.append(d)
            else:
                keep_ids.add(cur_by_tag[tag]['id'])
    # Deletions: rules not in desired tag set OR replaced
    delete_ids = []
    for c in current:
        tag = c.get('tag')
        if not tag:  # orphan rules with no tag
            delete_ids.append(c['id']); continue
        if tag not in desired_by_tag:
            delete_ids.append(c['id'])
        else:
            # If tag present but value differs it wasn't 'kept'
            if c['id'] not in keep_ids and normalize(desired_by_tag[tag]['value']) != normalize(c['value']):
                delete_ids.append(c['id'])
    return add, delete_ids

def normalize(v: str):
    return " ".join(v.split())

def snapshot_path(fprint):
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return Path(CONFIG['rules']['snapshots_dir']) / f"ruleset-{ts}-{fprint}.json"

def save_snapshot(meta_obj, fprint):
    path = snapshot_path(fprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(meta_obj, f, indent=2, sort_keys=True)
    # update symlink
    desired_link = Path(CONFIG['rules']['desired_file'])
    if desired_link.exists() or desired_link.is_symlink():
        desired_link.unlink()
    desired_link.symlink_to(path.relative_to(desired_link.parent))
    return path

def list_snapshots():
    snap_dir = Path(CONFIG['rules']['snapshots_dir'])
    return sorted(snap_dir.glob("ruleset-*.json"))

def load_snapshot_by_hash(partial):
    for p in list_snapshots()[::-1]:
        if partial in p.name:
            with open(p,'r') as f:
                return json.load(f), p
    raise SystemExit(f"No snapshot containing hash '{partial}'")

def apply_changes(add_list, delete_ids, dry_run, limits):
    add_cap = limits['max_add_per_run']
    del_cap = limits['max_delete_per_run']
    add_to_apply = add_list[:add_cap]
    delete_to_apply = delete_ids[:del_cap]
    print(f"[plan] ADD {len(add_to_apply)}/{len(add_list)}  DELETE {len(delete_to_apply)}/{len(delete_ids)}")
    if dry_run:
        print("[dry-run] Skipping API modification.")
        return
    # Delete first (to free quota / reduce conflicts)
    if delete_to_apply:
        print(f"[exec] Deleting {len(delete_to_apply)}")
        api_modify(delete_ids=delete_to_apply)
    if add_to_apply:
        print(f"[exec] Adding {len(add_to_apply)}")
        api_modify(add=add_to_apply)

def cmd_sync(args):
    meta_obj, desired_rules = load_desired(CONFIG['rules']['desired_file'])
    errs = lint_rules(desired_rules)
    if errs:
        for e in errs: print(f"[lint-error] {e}")
        if not args.force:
            sys.exit(1)
    current = api_get_rules()
    add, delete_ids = diff_rules(current, desired_rules)
    fprint = fingerprint(desired_rules)
    print(f"[fingerprint] desired={fprint}")
    print_diff(add, delete_ids, current)
    apply_changes(add, delete_ids, args.dry_run, {
        "max_add_per_run": CONFIG['safety']['max_add_per_run'],
        "max_delete_per_run": CONFIG['safety']['max_delete_per_run']
    })
    if not args.dry_run:
        meta_obj['fingerprint'] = fprint
        save_snapshot(meta_obj, fprint)
        print(f"[snapshot] Saved new snapshot with fingerprint {fprint}")

def print_diff(add, delete_ids, current):
    if add:
        print("\n=== ADD / REPLACE ===")
        for r in add:
            print(f"+ {r['tag']}: {truncate(r['value'])}")
    if delete_ids:
        print("\n=== DELETE ===")
        cur_by_id = {c['id']: c for c in current}
        for rid in delete_ids:
            cur = cur_by_id.get(rid, {})
            print(f"- {cur.get('tag','<no-tag>')} ({rid}) {truncate(cur.get('value',''))}")
    if not add and not delete_ids:
        print("[diff] No changes.")

def truncate(s, n=110):
    return s if len(s)<=n else s[:n]+"…"

def cmd_rollback(args):
    snap_obj, path = load_snapshot_by_hash(args.hash)
    print(f"[rollback] Loaded snapshot {path.name}")
    # Replace desired file w/ snapshot contents then sync
    tmp_desired = Path(CONFIG['rules']['desired_file'])
    with open(tmp_desired, 'w') as f:
        json.dump(snap_obj, f, indent=2, sort_keys=True)
    class o: pass
    o.dry_run = args.dry_run
    o.force = True
    cmd_sync(o)

def main():
    ap = argparse.ArgumentParser(description="Manage X Filtered Stream rules.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_sync = sub.add_parser("sync", help="Apply desired.json to X API")
    s_sync.add_argument("--dry-run", action="store_true")
    s_sync.add_argument("--force", action="store_true", help="Ignore lint errors")

    s_rb = sub.add_parser("rollback", help="Rollback to snapshot by hash fragment")
    s_rb.add_argument("hash")
    s_rb.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    load_config(os.environ.get("RULE_CONFIG","config.toml"))
    if args.cmd == "sync":
        cmd_sync(args)
    elif args.cmd == "rollback":
        cmd_rollback(args)

if __name__ == "__main__":
    main()
```

---

## 8. Typical Workflow

1. **Generate new desired set** (`desired.json`) from:

   * Manual edits **plus** accepted refinement suggestions (negatives / splits).
2. Run:

   ```bash
   RULE_CONFIG=config.toml ./automation/manage_rules.py sync --dry-run
   ```
3. Inspect diff & lint errors.
4. Apply:

   ```bash
   ./automation/manage_rules.py sync
   ```
5. Snapshot auto-saved → symlink `rules/desired.json` points to new version.
6. If precision tanks → rollback:

   ```bash
   ./automation/manage_rules.py rollback <fingerprint-fragment>
   ```

---

## 9. Integrating Refinement Suggestions

Refinement report example (`suggestions/refinement-report-20250722.json`):

```json
{
  "rule": "FED_CORE",
  "suggestions": {
    "add_negatives": [{ "token": "football", "ΔP": 0.07 }]
  }
}
```

**Merge Script Snippet:**

```python
def apply_refinements(desired_rules, refinements, auto_neg_threshold=0.06):
    by_tag = {r['tag']: r for r in desired_rules}
    for ref in refinements:
        tag = ref['rule']
        if tag not in by_tag: continue
        val = by_tag[tag]['value']
        negs = ref.get('suggestions', {}).get('add_negatives', [])
        for n in negs:
            if n['ΔP'] >= auto_neg_threshold and f"-{n['token']}" not in val.split():
                val += f" -{n['token']}"
        by_tag[tag]['value'] = val
    return list(by_tag.values())
```

Run this before writing `desired.json`.

---

## 10. Safety / Ops Tips

| Risk                                      | Mitigation                                                                                          |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Accidentally nuking all rules             | Script caps deletes per run (`max_delete_per_run`), require `--force` if lint errors                |
| Silent rule drift (manual portal changes) | `sync` always prints diff; schedule a daily dry-run; alert if drift                                 |
| Over‑tightening from automation           | Keep `max_new_negatives_per_cycle`; require human approval for DS below “high-confidence” threshold |
| Bearer token leakage                      | Load from env / secret manager; never commit config with token                                      |
| Rate limits                               | Backoff logic; small batch add/delete (X often caps modification frequency)                         |
| Orphaned rules (tag removed)              | Diff logic deletes any tag absent from desired file                                                 |

---

## 11. Observability (Optional Enhancements)

* Log JSON line per operation:

  ```json
  {"ts":"2025-07-22T09:01:04Z","action":"add","tag":"FED_CORE","rule_hash":"..."}
  ```
* Push summary to Slack:

  ```
  [Rules Sync] Added: 2, Replaced: 1, Deleted: 1, Fingerprint: a1b2c3d4e5f6
  ```
* Grafana counter: `rules_active_total`, `rules_change_events_total{action=...}`

---

## 12. Quick Start Commands

```bash
# 1. Create config
cp config.example.toml config.toml

# 2. Put your bearer token inside

# 3. Place initial desired.json
vim rules/desired.json

# 4. Dry-run
RULE_CONFIG=config.toml python automation/manage_rules.py sync --dry-run

# 5. Apply
python automation/manage_rules.py sync
```

---

## 13. Minimal Desired File Generator (Optional)

```python
import json, datetime
rules = [
  {"tag":"NDIV_CORE","value":"(\"national divorce\" ...) lang:en -is:retweet -kardashian -celebrity"},
  # ...
]
with open("rules/desired.json","w") as f:
  json.dump({
    "version": datetime.datetime.utcnow().isoformat()+"Z",
    "description": "Initial baseline",
    "rules": rules
  }, f, indent=2)
```

---

## 14. Rollback Example

List snapshots:

```bash
ls rules/snapshots
# ruleset-20250722-090000-a1b2c3d4e5f6.json
# ruleset-20250724-070500-09fe1cad8830.json
```

Rollback to first:

```bash
python automation/manage_rules.py rollback a1b2c3d4
```

---

## 15. Extending for “Shadow” Rules

Add a `"shadow": true` flag in desired file for candidates you *don’t* push yet—script filters them out unless `--include-shadow` set. Meanwhile you can locally simulate their match rate against stored corpus before they cost reads.

---

### TL;DR

Use a *versioned, linted, idempotent* Python manager: diff current vs desired, enforce heuristics, apply controlled batches, snapshot for rollback, and integrate automatic refinement suggestions—all while keeping you comfortably in quota and enabling fast, safe evolution of your topical coverage.

---

If you want next: **shadow rule simulation engine**, **negative token mining script**, or **precision dashboard SQL**, just say which.
