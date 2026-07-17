# Teammate end-to-end setup and deployment guide

This guide takes a teammate from repository access to a working, team-restricted
online property accessibility scorer. The application uses:

```text
Team browser -> Streamlit Community Cloud -> Supabase Postgres
                                      -> Public Overpass / OpenStreetMap
```

Supabase stores the shared assessment history and map-response cache. On a cache
miss, the Streamlit server sends the submitted coordinate to public Overpass to
retrieve OpenStreetMap road and POI data.

## 1. Before you start

You need:

- Access to this GitHub repository and permission to merge pull requests.
- A Supabase account that may create a project.
- A Streamlit Community Cloud account connected to the GitHub account that can
  access this repository.
- Permission to send submitted property coordinates to public Overpass services.
- Git and Python 3.11 or newer for local testing.

Do not commit property lists, occupancy data, database URLs, exported results,
or cache files. `.gitignore` is configured to exclude them.

## 2. Merge the application change

1. Open the current GitHub pull request that adds Supabase deployment support.
2. Review the changes, especially `scoring_service.py`, `requirements.txt`,
   `.streamlit/secrets.toml.example`, and this guide.
3. Merge it into `main`.
4. Confirm that `main` contains `streamlit_app.py`, `requirements.txt`, and
   `.streamlit/secrets.toml.example`.

For a more controlled rollout, deploy the pull-request branch first, test it,
then change the Streamlit deployment to use `main` after merging.

## 3. Create the Supabase database

1. Sign in to [Supabase](https://supabase.com/) and create a new project.
2. Record the project name, region, and database password in your approved
   password manager.
3. Wait until the project status is healthy.
4. In the Supabase dashboard, select **Connect**.
5. Copy the **Session pooler** connection string. This is the recommended
   connection type for a persistent Python web application using an IPv4-only
   hosting network.
6. Ensure that the URL includes `sslmode=require`. If there is no query string,
   append `?sslmode=require`; otherwise append `&sslmode=require`.

The final value resembles this example. Do not use the example literally:

```text
postgresql://postgres.PROJECT_REF:YOUR_PASSWORD@aws-REGION.pooler.supabase.com:5432/postgres?sslmode=require
```

Keep the complete URL secret. It grants database access and must never be placed
in source code, a screenshot, a chat message, or a Git commit.

The app creates its two tables automatically on its first successful request:

- `raw_cache` - shared OpenStreetMap/Overpass response cache
- `assessments` - saved scoring results and settings

No manual SQL migration is required for the initial setup.

## 4. Set up and test locally

### Windows

Open Command Prompt:

```cmd
git clone https://github.com/fnurrahmadi/accessibility-scoring.git
cd accessibility-scoring
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
mkdir .streamlit
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Open `.streamlit\secrets.toml` in a text editor and replace the example value:

```toml
DATABASE_URL = "paste the complete Supabase Session pooler connection string here"
```

Then start the app:

```cmd
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

### macOS or Linux

```bash
git clone https://github.com/fnurrahmadi/accessibility-scoring.git
cd accessibility-scoring
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and set `DATABASE_URL`, then run:

```bash
.venv/bin/python -m streamlit run streamlit_app.py
```

### Local test checklist

1. Open the URL printed in the terminal, normally `http://localhost:8501`.
2. Enter an authorised test latitude and longitude.
3. Leave both weights at 50 and calculate a score.
4. Confirm that the map, seven score cards, details table, and review flags
   render on the same page.
5. Refresh the page and confirm the assessment appears in **Saved assessments**.
6. Submit the exact coordinate again. Its source should show **Supabase cache**;
   this confirms the shared database cache works.
7. Download the CSV once and confirm it contains the assessment.

Do not proceed to online deployment until this checklist passes.

## 5. Deploy Streamlit Community Cloud

1. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Select **Create app** and choose this GitHub repository.
3. Select the `main` branch after the pull request is merged.
4. Set the entrypoint file to `streamlit_app.py`.
5. Choose an internal, non-sensitive app URL/subdomain.
6. Open **Advanced settings** and paste the following with the real secret:

   ```toml
   DATABASE_URL = "paste the complete Supabase Session pooler connection string here"
   ```

7. Deploy and wait for the build to finish.
8. Open the deployed URL and repeat the local test checklist.

Streamlit installs the packages listed in `requirements.txt` during deployment.
The database secret is configured in Streamlit Cloud, not stored in the GitHub
repository.

## 6. Restrict access before sharing

1. Open the deployed app's **Settings** in Streamlit Community Cloud.
2. Under sharing, select **Only specific people can view this app**.
3. Invite the approved team members.
4. Test with a non-authorised account if possible.
5. Share the URL only after access restrictions have been confirmed.

Do not make the app public while it uses public Overpass. An unrestricted app
allows unknown users to submit coordinates, creates uncontrolled map-data
requests, and exposes internal assessment history to app users.

## 7. Day-to-day operation

### Use the app

1. Enter the best available vehicle-arrival latitude and longitude.
2. Adjust the connectivity and road-width weights if the business-approved
   scenario requires it. The overall score normalises the two weights, so 50/50
   and 100/100 have the same relative weighting.
3. Calculate the score and review the map, component scores, detail fields, and
   flags.
4. Treat low data confidence or access/road flags as a manual-review trigger,
   not an automatic rejection.
5. Use the CSV export when an authorised user needs the saved assessment data.

### Update the app

1. Create a Git branch for the change.
2. Test locally with the Supabase secret.
3. Open and review a pull request.
4. Merge into `main`.
5. Streamlit Community Cloud redeploys from the repository; confirm the new
   deployment is healthy.

### Back up and recover

- Supabase owns the durable assessment/cache data. Use its dashboard and your
  organisation's approved backup process for data retention.
- GitHub contains application source and documentation, not operational data.
- If a deployment fails, use Streamlit's previous-deployment controls or revert
  the GitHub commit, then confirm the app can reconnect to Supabase.

## 8. Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `DATABASE_URL is not configured` | Secret is missing or misnamed. | Add `DATABASE_URL` to `.streamlit/secrets.toml` locally or Streamlit Cloud Secrets online, then restart/redeploy. |
| Password/authentication error | Wrong connection string or password. | Copy the Session pooler string again from Supabase Connect and check URL encoding for special password characters. |
| Connection timeout/refused | Supabase project is paused, unhealthy, or URL uses an unsuitable endpoint. | Check Supabase project health and use the Session pooler connection string with SSL. |
| App loads but saved history is empty | App points to a different database or a new project. | Confirm the exact `DATABASE_URL` secret and submit a test score. |
| Score fails after a wait | Public Overpass is busy or unavailable. | Try again later. Repeated locations are served from Supabase cache once successfully retrieved. |
| Unexpected public access | Sharing is set to public. | Change Streamlit sharing to approved people only and review who has repository access. |

## 9. Ownership checklist

Before handing the app to business users, the teammate should confirm:

- [ ] The GitHub repository and Streamlit app have appropriate access control.
- [ ] The Supabase connection string exists only in approved secret stores.
- [ ] A permitted test score has completed and is visible in saved history.
- [ ] The deployed app is restricted to approved viewers.
- [ ] The team understands that coordinates go to public Overpass on cache misses.
- [ ] A named owner is responsible for Supabase/Streamlit account renewal,
      usage quotas, and access reviews.
- [ ] The team understands batch upload is not yet available in the Streamlit UI.
