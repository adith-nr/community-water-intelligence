# Community Water Intelligence

A local pilot for reporting household water observations in Prayagraj and following a reviewer-led investigation. The map shows generalized complaint locations alongside historical CPCB river stations. All residents, household complaints and incident outcomes are fictional.

## Run locally

```sh
docker compose up --build -d
docker compose exec -T api python -m pytest -q
```

Open [the pilot](http://localhost:3000). The API docs are at [localhost:8000/docs](http://localhost:8000/docs). Compose migrates PostgreSQL and seeds the pilot on startup. The existing data volume is reused.

Set `GROQ_API_KEY` and `REVIEWER_TOKEN` in the local `.env` when setting up another copy. The existing workspace already has both. Copy the value of `REVIEWER_TOKEN` from that file to sign into the Review tab. The pilot account selector intentionally allows switching among three fictional households. Run the app on localhost.

## Walk through the pilot

1. Open the map as Resident 1. Select the Riverside discolouration incident to see three matched households. North has a resolved borewell incident and an unverified particles report. Switch residents and open **My reports** to see the individual submissions.
2. To test new clustering, choose a category such as **low pressure** and submit a report from each resident. Use the same locality and supply type and keep the default map position. The first two households stay unverified. The third creates an emerging incident. Repeat a report from one account to confirm it still counts as one household.
3. In **Review**, sign in and select Riverside. Run a Groq investigation. Open the cited evidence and read the draft. Approve it to deliver an in-app alert to opted-in residents. Resident 1 is subscribed to Riverside by default. Residents 2 and 3 start opted out.
4. Open **Alerts** as Resident 1. Use **Report a similar issue** or change the subscription. In **Review**, record a finding, start investigation, then resolve it with a documented reason. Reopen it from Review or submit another matching report within the 72-hour window.

## Data and decisions

- The two Prayagraj PDFs and Uttar Pradesh CPCB CSV are mounted read-only. The [source catalog](reports/sources.json) records their URLs and checksums. The app reads them directly, caches PDF text in memory, links exact PDF pages, and extracts numeric river observations with CSV line references when present. The supplied CSV includes station locations, but matching river rows have no usable numeric readings. Scan-only pages require text extraction before they can appear in search.
- Historical rainfall comes from Open-Meteo. Missing or unavailable observations appear explicitly. River and weather measurements provide context. Supply connections and contamination causes remain unknown.
- LangGraph runs three structured Groq calls for evidence selection, follow-up checks and alert emphasis. Code verifies evidence IDs and renders bounded public wording. Alert delivery is transactional, in-app only, and requires the reviewer token.
- The pilot uses three seeded identities as household IDs, a 72-hour correlation window, and a 1 km fallback when a shared reported zone is unavailable. Public pins use locality centroids. Optional photos are re-encoded without metadata and stored privately.
- Migrations add reports, incidents, investigation runs, audit events, drafts and deliveries. The frontend uses a small standalone runtime and the project requires no host-side frontend dependency install.

The seeded Riverside and North incident scenarios include labelled simulated river and rainfall measurements. These values illustrate different lines of inquiry and do not establish the cause of household complaints.

## River watch

Simulated Sangam and Rasoolabad river devices expose hourly pH, turbidity and dissolved oxygen readings. Sangam's sustained turbidity and dissolved-oxygen change creates a Riverside draft at startup, independent of household complaints. The rule is a simulation trigger. Reviewers can open its evidence and approve delivery to opted-in Riverside residents.

Set `GNEWS_API_KEY` in `.env` and recreate the API to use GNews. Without a key, headline search uses GDELT. In **Review**, select the river sensor anomaly and use **Check river watch** to refresh headlines. Groq selects relevant results. Publisher, date or index timestamp, and original links appear when available. Headline context does not establish a connection to the simulated readings.
