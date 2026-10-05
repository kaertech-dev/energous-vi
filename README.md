# energous-vi

## Configuration

Create a `.env` file from `.env.example` and set a unique `SECRET_KEY`,
`ADMIN_PASSWORD`, and the database connection values before starting the app.
The app exits during startup if any required value is missing.

Run with `docker compose up --build`. The container uses Gunicorn and stores
timestamps in the `Asia/Manila` timezone. VI reads unit state from `energous.esense_main`, and
VI scan records and admin reports use `energous.esense_vi_copy`.
