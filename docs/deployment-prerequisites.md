# Deployment prerequisites — what to get onto a server before `./build.sh`

This covers everything a fresh server needs before running `./build.sh`
(repo root), which brings up Snowstorm Lite, the API (with MedCAT
in-process), and the GUI.

## 1. The repository

```bash
git clone <this-repo-url>
cd ctakes-rest-service-docker
```
(or `git pull` if it's already there).

## 2. The MedCAT model pack

The API loads this from a host path mounted into its container — it is
**not** part of the repo and is **not** downloaded by any build script (it's
a licensed, multi-gigabyte artifact — see `docs/ctakes-to-medcat-migration.md`
and `api/README.md` for how to obtain one).

Copy the model pack directory from wherever you downloaded/unpacked it to
the server, at the path `api/start.sh` expects by default
(`$HOME/medcat_models/model_pack`):

```bash
scp -r ~/medcat_models/model_pack your-user@your-server:~/medcat_models/model_pack
```

If you'd rather keep it elsewhere on the server, set
`MEDCAT_MODEL_PACK_HOST_PATH` before running `./build.sh` (it's read by
`api/start.sh`).

## 3. `.env`

The root `.env` holds real secrets (`API_BEARER_TOKEN`, `API_BEARER_TOKEN_HASH`,
`OPENAI_API_KEY`) — it is gitignored and must be copied out-of-band, never
committed:

```bash
scp .env your-user@your-server:~/ctakes-rest-service-docker/.env
```

Required variables (see `api/README.md` for the full table): `OPENAI_API_BASE`,
`OPENAI_API_KEY`, `OPENAI_MODEL_ID`, `API_BEARER_TOKEN`,
`API_BEARER_TOKEN_HASH`, `SNOWSTORM_URL`, `SNOWSTORM_BRANCH`,
`MEDCAT_MODEL_PACK_PATH`.

## 4. SNOMED CT RF2 archive (for Snowstorm onboarding)

Snowstorm Lite starts empty. Once it's running (`./build.sh` starts it), copy
your licensed SNOMED CT RF2 release archive to the server and onboard it:

```bash
scp SnomedCT_RF2Release_INT_PRODUCTION.zip your-user@your-server:~/
python scripts/snomed/snomed_rf_refresh.py \
  --archive-path ~/SnomedCT_RF2Release_INT_PRODUCTION.zip \
  --base-url http://localhost:8083
```

## Order of operations on a fresh server

1. `git clone` the repo.
2. `scp -r` the MedCAT model pack to `~/medcat_models/model_pack`.
3. `scp` the root `.env` into the repo.
4. `scp` the SNOMED CT RF2 archive (or run onboarding later, once Snowstorm is up).
5. `./build.sh` — brings up Snowstorm Lite, the API, and the GUI.
6. Run `scripts/snomed/snomed_rf_refresh.py` against `http://localhost:8083` if step 4's archive wasn't onboarded yet.
7. Verify: `curl http://localhost:8082/health` and `curl http://localhost:8082/generate/medcat/health` (with the bearer token), then open `http://localhost:8081` for the GUI.
