# Online deployment: Streamlit Community Cloud and Supabase

This deployment uses Streamlit Community Cloud for the web application and
Supabase Postgres for the shared assessment history and Overpass-response cache.
The browser never receives the database connection string.

## 1. Create the Supabase database

1. Sign in to [Supabase](https://supabase.com/) and create a project.
2. Save the database password in your approved password manager.
3. In the project dashboard, select **Connect** and copy the **Session pooler**
   connection string. Session pooling is the appropriate Supabase option for a
   persistent Python web application running from an IPv4-only hosting network.
4. Add `sslmode=require` to the connection string if it is not already present.
5. Keep this complete string secret. Do not add it to GitHub or expose it in the
   Streamlit page.

On the app's first successful request, it automatically creates the `raw_cache`
and `assessments` tables. No manual SQL migration is required.

## 2. Test locally with the hosted database

Create a file named `.streamlit/secrets.toml` by copying
`.streamlit/secrets.toml.example`, then replace the example value:

```toml
DATABASE_URL = "your complete Supabase Session pooler connection string"
```

Run the app:

```cmd
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The secret file is ignored by Git. Verify that a score can be calculated and that
the saved-assessment section loads before deploying.

## 3. Deploy from GitHub

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) with the GitHub
   account that can access this repository.
2. Select **Create app**, choose the repository and `main` branch, and set the
   entrypoint file to `streamlit_app.py`.
3. In **Advanced settings**, paste this into the Secrets field, using the real
   connection string:

   ```toml
   DATABASE_URL = "your complete Supabase Session pooler connection string"
   ```

4. Deploy, then calculate one test location.
5. In the app settings, set sharing to **Only specific people can view this app**
   and invite the intended team members. A public app would let unknown users
   submit locations and consume the public Overpass request allowance.

## Security and operational notes

- Keep the GitHub repository private if its commit history, configuration, or
  internal methodology should not be public. The current source contains no
  database credential or property input data.
- Use only the database connection string in Streamlit secrets. Do not place a
  Supabase service-role key in this application.
- The app sends an uncached property coordinate to public Overpass services.
  Inform authorised users of this data flow.
- The app shares one Supabase cache across all users, so a repeated location does
  not create another Overpass request.
- Free-plan quotas, pausing rules, and access features are controlled by
  Supabase and Streamlit and should be checked before operational use.
