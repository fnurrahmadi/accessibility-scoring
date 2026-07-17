# Property accessibility scorer

A Streamlit proof of concept for scoring the vehicle accessibility of a new
hospitality property from its latitude and longitude. It retrieves nearby
OpenStreetMap data through public Overpass services and presents a 0–100
accessibility result with diagnostic component scores.

This repository is designed to be cloned by another person and run under their
own account. No property list, occupancy data, raw map cache, or saved
assessments are required to use the single-property app. A Supabase database is
required for the Streamlit application.

## What the app does

1. A user enters a latitude and longitude.
2. The app displays the location on a map.
3. It obtains road and nearby-place data from public Overpass/OpenStreetMap
   services, unless the exact location is already cached.
4. It calculates and displays:
   - overall accessibility score
   - connectivity score
   - road-width score
   - vehicle-access score
   - guest-convenience score
   - operational-access score
   - data-confidence score
5. It saves results in Supabase Postgres and lets the user download assessment
   history as CSV.

The overall score is an adjustable additive combination of connectivity and
road width. The default is 50/50.

## Important use and privacy notes

- This is a screening tool, not an automatic property approval or rejection
  decision.
- For an uncached location, the submitted coordinates are sent to public
  Overpass services to retrieve OpenStreetMap features. Do not use it for
  coordinates you are not permitted to share with those services.
- Public Overpass is suitable for this low-volume POC. Use a managed map-data
  service or a self-hosted instance before relying on it for high-volume or
  business-critical production traffic.
- Road width and access tags may be incomplete in OpenStreetMap. Check the
  data-confidence score and review flags before making a decision.

## Set up on Windows

### Prerequisites

- Git
- Python 3.11 or later (install it from [python.org](https://www.python.org/downloads/))
- A GitHub account, if you are cloning from GitHub

### Install, configure, and run

Open **Command Prompt** and run the following, replacing the GitHub URL with
the repository URL supplied to you:

```cmd
git clone https://github.com/OWNER/REPOSITORY.git
cd REPOSITORY
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Before the final command, create `.streamlit\secrets.toml` by copying
`.streamlit\secrets.toml.example` and replace `DATABASE_URL` with the Supabase
**Session pooler** connection string. Full database and online-deployment steps
are in [DEPLOYMENT.md](DEPLOYMENT.md).

The terminal will show a local URL, normally `http://localhost:8501`. Open that
address in a browser. For future starts, either run the final command again or
double-click `start_accessibility_app.cmd`.

## Set up on macOS or Linux

```bash
git clone https://github.com/OWNER/REPOSITORY.git
cd REPOSITORY
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run streamlit_app.py
```

Before running Streamlit, copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and configure `DATABASE_URL` as described in
[DEPLOYMENT.md](DEPLOYMENT.md).

## Prepare and push your own GitHub repository

The person creating the repository should:

1. Create a new **private** GitHub repository.
2. Copy this project into it.
3. Confirm that `.gitignore` is present before the first commit. It excludes
   private property/occupancy inputs, secrets, caches, and output files.
4. Review the files staged for commit. Do not upload private coordinate data or
   exported assessment data unless this has been explicitly approved.
5. Commit and push the source code. Collaborators can then clone it using the
   setup instructions above.

The single-property app does not require `properties.csv` or `occupancy.csv`.
Those files are only needed for the separate batch POC and performance-analysis
scripts. A collaborator who is authorised to run those scripts should obtain
the input files through your approved internal data-sharing process, not from
the repository by default.

## Configuration

[`config.json`](config.json) contains the POC settings:

- public Overpass endpoints
- road and POI search radii
- request delay, timeout, and retry count
- default overall-score weights
- score thresholds and road-width fallbacks

Changes to this file affect all new assessments. Keep the configuration under
version control so scoring remains reproducible.

## Optional: batch POC scripts

The repository also contains the original batch scoring and evaluation scripts.
They are optional and are not required for the Streamlit app. After an
authorised user has placed `properties.csv` in the project root, inspect the
planned sample without calling Overpass:

```cmd
.venv\Scripts\python.exe accessibility_poc.py --dry-run
```

Run the default 100-property POC:

```cmd
.venv\Scripts\python.exe accessibility_poc.py
```

Batch upload in the Streamlit interface and a downloadable CSV template are
planned future enhancements.

## Deploy online

The application is prepared for deployment with Streamlit Community Cloud and
Supabase Postgres. Follow the complete [teammate setup and deployment guide](DEPLOYMENT.md)
to set up local development, create the database, configure secrets, deploy from
GitHub, restrict access, test, operate, and troubleshoot the app.
