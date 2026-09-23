# Deploying to DigitalOcean

The service runs on **DigitalOcean App Platform**, built from this repository's `Dockerfile`,
with a **managed PostgreSQL** database attached. Everything is described in
[`.do/app.yaml`](../.do/app.yaml), so a deploy is one command and can be repeated at any time.

```
GitHub (main) ──build──► App Platform (container, HTTPS) ──► Managed Postgres (dev database)
                          BASE_URL, DATABASE_URL injected at runtime
```

## Cost

Both resources are billed while they exist (rates from DigitalOcean's
[pricing page](https://docs.digitalocean.com/products/app-platform/details/pricing/)):

| Resource | Size | Price |
|---|---|---|
| App Platform service | `apps-s-1vcpu-0.5gb` | $5.00 / month |
| Development database | 512 MB | $7.00 / month |

Delete both when you are done practising (see [Tear down](#7-tear-down)). Check your DigitalOcean
billing page for how usage is prorated; that is not covered here.

## 1. Prerequisites

- A DigitalOcean account.
- `doctl` installed: `brew install doctl` (pre-installed on the interview workstation).
- This repository pushed to GitHub (it is public: `zhangjames01/JZ_URL_Shortener`).

## 2. Authenticate `doctl` (once per machine)

1. In the DigitalOcean console go to **API → Tokens → Generate New Token**. Give it read and write
   access to Apps and Databases (or full access for a practice run).
2. Run the command below and paste the token when prompted. **Do this yourself; never paste the
   token into a chat, a file, or the repository.**

```bash
doctl auth init
```

3. Check that it worked:

```bash
doctl account get
```

Revoke the token in the console when you are finished.

## 3. First deploy

```bash
doctl apps create --spec .do/app.yaml --wait --format ID,DefaultIngress,Created
```

- `--wait` blocks until the first deployment finishes (several minutes: it builds the image and
  provisions the database).
- The output shows the **app ID** and the public URL (`https://url-shortener-xxxxx.ondigitalocean.app`).
  Save both. If you lose the ID later: `doctl apps list`.

## 4. Verify the deployment

Replace `$URL` with the `DefaultIngress` value.

```bash
URL=https://url-shortener-xxxxx.ondigitalocean.app

curl -s $URL/healthz
```

```bash
curl -s -X POST $URL/api/v1/urls -H 'content-type: application/json' \
  -d '{"url": "https://example.com/hello", "alias": "hello"}'
```

```bash
curl -i $URL/hello
```

```bash
curl -s $URL/api/v1/urls/hello
```

Expected: `{"status":"ok"}`, a `201` whose `short_url` starts with your app URL, a `302` with
`location: https://example.com/hello`, and metadata showing `click_count` 1.

To prove persistence, redeploy (step 5) and fetch the metadata again: the link and its click
count must still be there.

## 5. Redeploy after a code change

`deploy_on_push: true` is set, so **every push to `main` deploys automatically**. Note this does
not wait for CI; a push that breaks the tests still deploys. Watch it:

```bash
doctl apps list-deployments <APP_ID>
```

To force a deployment without a push:

```bash
doctl apps create-deployment <APP_ID>
```

## 6. Change configuration (env vars, size, instance count)

Edit `.do/app.yaml`, then apply it:

```bash
doctl apps update <APP_ID> --spec .do/app.yaml
```

The spec in the repository is the source of truth; avoid changing settings in the console, or the
next `update` will overwrite them.

### Logs

```bash
doctl apps logs <APP_ID> web --type run --follow
```

```bash
doctl apps logs <APP_ID> web --type build
```

## 7. Tear down

```bash
doctl apps delete <APP_ID>
```

Then confirm the database is gone. This guide has not verified whether deleting the app also
deletes its development database, so always check:

```bash
doctl databases list
```

If a database is still listed, delete it by its ID from that output (`doctl databases delete <DB_ID>`).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `access token is required` | Run `doctl auth init` (step 2). |
| Create fails with a GitHub authorization error | DigitalOcean has not been granted access to read your GitHub repository. In the console choose **Create App → GitHub** once and authorize DigitalOcean, then rerun the command. |
| Deployment stuck or failing health checks | Read the run logs (above). A startup failure to reach the database is reported there, because the app opens its database connections at startup. |
| App cannot connect to the database (SSL / connection errors) | The spec sets `PGSSLMODE=require`. If the error persists, print the run logs and check that the `db` component exists in `doctl apps get <APP_ID>`. |
| `short_url` shows the wrong host | `BASE_URL` comes from `${APP_URL}`. After adding a custom domain, `APP_URL` follows the primary domain automatically. |
| Build fails | Read the build logs. Make sure the image builds locally: `docker build -t url-shortener .` |

## What this setup does not do

- **No backups or standby**: it is a development database. For a real launch use a managed cluster
  (`production: true` in the spec) and see DigitalOcean's backup options.
- **No CI gate on deploys**: pushes deploy even if CI fails.
- **No custom domain or rate limiting.**
- **Not verified by this guide:** the exact contents of the injected `DATABASE_URL` (the spec sets
  `PGSSLMODE=require` so TLS does not depend on it), and dev-database cleanup behaviour on app deletion.
