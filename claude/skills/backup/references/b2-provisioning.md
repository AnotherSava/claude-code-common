# Provisioning a Backblaze bucket and its scoped key

Read this when a project needs a repository it does not have yet. Everything here runs from a workstation
over B2's **native** API — HTTP Basic to `b2_authorize_account`, then plain JSON. No SigV4 signer, no
`b2` CLI, no console.

`~/.claude/learnings/restic-backblaze-b2-backups.md` has the reasoning behind every choice below. This
file is the procedure only.

## The credential, and what it may do

`B2_MASTER_KEY` in Doppler `tools/prd`, with `B2_MASTER_KEY_ID` beside it. The master key's keyID **is
the account id** — it has no separate id — and it lives in Doppler rather than in this file because this
repository is public: the id is not a credential on its own, but publishing it narrows the target for
anyone who later finds the secret.

Why the master key and not an ordinary one: a console-created "All buckets / Read and Write" key carries
`writeBuckets` and could create the bucket, but `writeKeys` is not grantable through that form. Minting
the per-project scoped key needs the master key or a console trip per project.

**Authorized without asking** — all additive, all cheap to undo:

- create a bucket for a project that has none
- set that bucket's lifecycle rule
- mint an application key scoped to that bucket
- store the resulting id/secret in **that project's** Doppler config
- `restic init` into the new, empty repository

**Ask first** — irreversible, or someone else's:

- deleting a bucket, a key, or any snapshot
- touching a bucket or key that belongs to another project
- changing the lifecycle rule on a bucket that already holds backups
- `restic forget` / `prune` run by hand
- rotating `B2_MASTER_KEY`

**Never** put `B2_MASTER_KEY` on the box. It is a workstation credential; the box gets a key scoped to one
bucket, and only that.

## Provision

One script, run from a workstation. It is idempotent on the bucket (it refuses to recreate one that
exists) and it stores the key's secret directly into Doppler, because B2 returns it exactly once.

Substitute `<project>` (the Doppler project) and `<bucket>` (conventionally `<project>-backups`).

```bash
B2MK=$(doppler secrets get B2_MASTER_KEY -p tools -c prd --plain) \
B2ID=$(doppler secrets get B2_MASTER_KEY_ID -p tools -c prd --plain) python3 <<'EOF'
import base64, json, os, subprocess, urllib.request, urllib.error

ACCOUNT_ID = os.environ['B2ID']      # the master key's keyID IS the account id
PROJECT    = '<project>'
BUCKET     = '<bucket>'

# "Keep only the last version of the file". MANDATORY for the S3-compatible endpoint: that backend only
# HIDES what it deletes, so without this `forget --prune` reclaims nothing while every run exits 0.
LIFECYCLE = [{'fileNamePrefix': '', 'daysFromHidingToDeleting': 1, 'daysFromUploadingToHiding': None}]

# Exactly what restic's S3 backend issues — ListBucket, GetObject, PutObject, DeleteObject. Delete is
# required because prune deletes; a read-only key fails only at the prune step, months in.
# listAllBucketNames is the "Allow List All Bucket Names" checkbox; without it S3 ListBuckets 403s.
CAPS = ['listBuckets', 'listAllBucketNames', 'listFiles', 'readFiles',
        'shareFiles', 'writeFiles', 'deleteFiles']

auth = base64.b64encode(f"{ACCOUNT_ID}:{os.environ['B2MK']}".encode()).decode()
req = urllib.request.Request('https://api.backblazeb2.com/b2api/v3/b2_authorize_account',
                             headers={'Authorization': f'Basic {auth}'})
d = json.load(urllib.request.urlopen(req, timeout=30))
api, token = d['apiInfo']['storageApi']['apiUrl'], d['authorizationToken']
s3 = d['apiInfo']['storageApi']['s3ApiUrl']

def call(name, payload):
    r = urllib.request.Request(f'{api}/b2api/v3/{name}', data=json.dumps(payload).encode(),
                               headers={'Authorization': token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.load(resp), None
    except urllib.error.HTTPError as e:
        return None, json.loads(e.read().decode() or '{}')

found, _ = call('b2_list_buckets', {'accountId': ACCOUNT_ID, 'bucketName': BUCKET})
if (found or {}).get('buckets'):
    bucket = found['buckets'][0]
    print(f'bucket {BUCKET} already exists — not recreating')
else:
    bucket, err = call('b2_create_bucket', {'accountId': ACCOUNT_ID, 'bucketName': BUCKET,
                                            'bucketType': 'allPrivate', 'lifecycleRules': LIFECYCLE})
    if err:
        raise SystemExit(f'CREATE BUCKET FAILED: {err}')
    print(f'created {BUCKET} ({bucket["bucketId"]}, {bucket["bucketType"]})')
print('  lifecycleRules:', json.dumps(bucket.get('lifecycleRules')))

key, err = call('b2_create_key', {'accountId': ACCOUNT_ID, 'keyName': f'{PROJECT}-vps-backup',
                                  'capabilities': CAPS, 'bucketId': bucket['bucketId']})
if err:
    raise SystemExit(f'CREATE KEY FAILED: {err}')
print(f'created key {PROJECT}-vps-backup, scoped to {bucket["bucketId"]}')

def put(name, value):
    p = subprocess.run(['doppler', 'secrets', 'set', name, '-p', PROJECT, '-c', 'prd', '--silent'],
                       input=value, text=True, capture_output=True)
    print(f'  {name}: {"stored" if p.returncode == 0 else "FAILED " + p.stderr[:120]}')

put('AWS_ACCESS_KEY_ID', key['applicationKeyId'])
put('AWS_SECRET_ACCESS_KEY', key['applicationKey'])
print(f'\nRESTIC_REPOSITORY=s3:{s3.split("//")[1]}/{BUCKET}/<host>')
EOF
```

The last line prints the repository URL to store as `RESTIC_REPOSITORY`. Use the **host name** as the path
segment, not a generic one — a second host then gets its own repository in the same bucket.

## Verify, by round-tripping through Doppler

Never trust the creation output alone; read the credential back from where the box will read it.

```bash
python3 <<'EOF'
import base64, json, subprocess, urllib.request
g = lambda k: subprocess.run(['doppler','secrets','get',k,'-p','<project>','-c','prd','--plain'],
                             capture_output=True, text=True).stdout.strip()
a = base64.b64encode(f"{g('AWS_ACCESS_KEY_ID')}:{g('AWS_SECRET_ACCESS_KEY')}".encode()).decode()
r = urllib.request.Request('https://api.backblazeb2.com/b2api/v3/b2_authorize_account',
                           headers={'Authorization': f'Basic {a}'})
sa = json.load(urllib.request.urlopen(r, timeout=25))['apiInfo']['storageApi']
print('scoped to :', sa.get('bucketName'), sa.get('bucketId'))
print('caps      :', sorted(sa.get('capabilities', [])))
print('s3 endpoint:', sa.get('s3ApiUrl'))
EOF
```

**You must see** the bucket you just created, seven capabilities, and no bucket-management rights. A key
that reports `bucketId: None` is account-wide and must not go on the box.

## Reading a bucket's lifecycle rule later

The same bucket-scoped key can read its own bucket's rules and list file versions — which is what makes
the lifecycle blind spot checkable from the box rather than merely known about:

```
b2_list_buckets        -> buckets[0].lifecycleRules
b2_list_file_versions  -> files[].action == "hide"   (hide markers awaiting collection)
```

Assert the rule's **shape**, not its presence. A rule whose `fileNamePrefix` scopes it elsewhere never
touches this repository, and one with `daysFromUploadingToHiding` set hides live backup data on a timer.
Both read as "a lifecycle rule exists".
