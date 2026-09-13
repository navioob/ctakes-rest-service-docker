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

Drops into `medcat_models/model_pack` at the repo root — gitignored, not
part of the repo, not downloaded by any build script (it's a licensed,
multi-gigabyte artifact — see `docs/ctakes-to-medcat-migration.md` and
`api/README.md` for how to obtain one). `api/start.sh` defaults to reading
it from exactly that repo-relative path, on both your machine and the
server, so nothing needs configuring once it's there.

**`deploy.sh`** (repo root) copies the model pack, any SNOMED CT RF2
archive (see §4), and `.env` to a server over SSH in one go. Edit the
`REMOTE_USER`/`REMOTE_HOST`/`REMOTE_REPO_PATH` variables at its top, then:

```bash
./deploy.sh
```

If you'd rather keep the model pack elsewhere on the server, set
`MEDCAT_MODEL_PACK_HOST_PATH` before running `./build.sh` there.

## 3. `.env`

The root `.env` holds real secrets (`API_BEARER_TOKEN`, `API_BEARER_TOKEN_HASH`,
`OPENAI_API_KEY`) — it is gitignored and must be copied out-of-band, never
committed. `deploy.sh` (above) does this along with the model pack and SNOMED archive;
manually it's:

```bash
scp .env your-user@your-server:~/ctakes-rest-service-docker/.env
```

Required variables (see `api/README.md` for the full table): `OPENAI_API_BASE`,
`OPENAI_API_KEY`, `OPENAI_MODEL_ID`, `API_BEARER_TOKEN`,
`API_BEARER_TOKEN_HASH`, `SNOWSTORM_URL`, `SNOWSTORM_BRANCH`,
`MEDCAT_MODEL_PACK_PATH`.

## 4. SNOMED CT RF2 archive (for Snowstorm onboarding)

Drops into `scripts/snomed/data/` at the repo root — also gitignored (the
bare `data` pattern), same convention as the model pack. `deploy.sh` copies
whatever's in that directory to the same repo-relative path on the server
(skips this step with a message if the directory is empty locally).

`./build.sh` handles onboarding itself now: it waits for Snowstorm Lite to
come up, checks whether SNOMED is already loaded (data persists across
container recreation in a named Docker volume, so this is normally only
needed once per fresh volume), and if not, auto-onboards the first `.zip`
it finds in `scripts/snomed/data/`. No manual step needed as long as the
archive is there before running `./build.sh` — it just warns and continues
if the directory's empty.

To onboard manually instead:

```bash
python scripts/snomed/snomed_rf_refresh.py \
  --archive-path scripts/snomed/data/SnomedCT_InternationalRF2_PRODUCTION_<date>.zip \
  --base-url http://localhost:8083
```

## Order of operations on a fresh server

1. `git clone` the repo, on both your machine (if not already) and the server.
2. Drop the MedCAT model pack into `medcat_models/model_pack` on your machine.
3. Drop your licensed SNOMED CT RF2 archive into `scripts/snomed/data/` on your machine.
4. `./deploy.sh` (after editing its `REMOTE_*` vars) — copies the model pack, SNOMED archive, and `.env` to the server.
5. On the server: `./build.sh` — checks the model pack is present, brings up Snowstorm Lite, auto-onboards SNOMED if the volume is empty, then starts the API and the GUI.
6. Verify: `curl http://localhost:8082/health` and `curl http://localhost:8082/generate/medcat/health` (with the bearer token), then open `http://localhost:8081` for the GUI.
