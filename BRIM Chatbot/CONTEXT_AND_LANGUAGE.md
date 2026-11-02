# Context, language and greeting

This document covers the contextual greeting and multilingual layer: what it calls, what it
stores, and how to change it.

## Flow

```
browser context (language, local hour, optional city)
        ↓
GreetingService  ── holiday?  (wins)
        │        └─ notable weather?  (only sometimes)
        └─ time of day (morning / afternoon / evening / late night)
        ↓
message catalogue (en · hi · gu · mr)
        ↓
stored as the conversation's first assistant message
```

The greeting is created once per conversation, inside `POST /api/conversations`, and stored as a
normal message. Reloading the page replays it; it is not regenerated per render.

## Supported languages

`en` English · `hi` हिन्दी · `gu` ગુજરાતી · `mr` मराठी

Selection order: explicit picker → script/word detection of the message → `navigator.language` →
English.

- Scripts are detected directly (Devanagari, Gujarati); Devanagari is split into Hindi vs Marathi
  using function words (`आहे`, `मला`, `पाहिजे` …).
- Romanised Hindi/Gujarati is detected from common words (`mujhe`, `chahiye`, `mane`, `joiye`).
- A three-or-more-word English message switches a Hindi thread back to English; a stray token like
  "3 BHK" does not.
- Switching language changes wording only. Slots (location, BHK, budget, stage, lead progress) are
  preserved — `tests/test_context_language.py` asserts this in both directions.

To add a language: copy a block in `app/core/messages.py`, translate the values, and add the code
to `SUPPORTED_LANGUAGES` (and to `LANGUAGE_OPTIONS` in `frontend/src/services/contextService.js`).

## Location

Optional and never required.

1. `contextService.getContext()` asks the browser for geolocation (once, with a 6 s cap).
2. If granted, the coordinates are used for a single reverse-geocode request and **discarded**.
3. Only the resulting city/region label is sent to our API.
4. If denied, `brim_location_denied` is stored locally and the greeting uses time of day only.

`POST /api/conversations` accepts `city`, `region`, `local_hour`, `utc_offset_minutes`,
`location_granted`, `language`, `language_hint`. It has no coordinate fields.

## Privacy

- Coordinates are never stored, logged, or sent to our backend.
- Conversation state stores `language`, `city`, `region`, `time_of_day`, `location_granted` — no
  precise location, no IP, no device identifiers.
- Denying permission has no functional cost: the chat, the flow and lead capture all work.
- The greeting endpoint is public so an embedded widget can call it before login; it reads no user
  data.

## External APIs

| Purpose | Endpoint | Key | Called when | Failure behaviour |
|---|---|---|---|---|
| Reverse geocoding (browser) | `api.bigdatacloud.net/data/reverse-geocode-client` | none | location granted | greeting falls back to time only |
| Weather geocoding | `geocoding-api.open-meteo.com/v1/search` | none | greeting with a city | no weather sentence |
| Weather forecast | `api.open-meteo.com/v1/forecast` | none | greeting with a city | no weather sentence |
| Optional LLM (browser) | Puter via `@heyputer/puter.js` | Puter session | `VITE_USE_PUTER=true` | keeps the server answer |

Weather lookups are cached in memory for 15 minutes per city and never raise into the chat path.

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `WEATHER_ENABLED` | `true` | `false` disables the weather provider entirely |
| `WEATHER_PROVIDER` | `open-meteo` | `none` uses a null provider |
| `WEATHER_MENTION_PROBABILITY` | `0.35` | chance a pleasant-weather greeting mentions weather; notable weather (rain, heat, cold) always may |
| `ENGAGEMENT_ENABLED` | `true` | allows one optional light question ("tea or coffee?") on the opening greeting |
| `HOLIDAY_FILE` | `demo_documents/holidays.json` | festival calendar path |
| `VITE_USE_PUTER` | `false` | routes knowledge answers through Puter when enabled |
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | API base for the SPA |

## Holidays

`demo_documents/holidays.json` holds `{date, name, names{lang}}` rows. A holiday outranks weather
and time-of-day. Edit the file (no restart needed — it is re-read when the file changes) or point
`HOLIDAY_FILE` at a managed calendar.

## Testing

```bash
cd backend
python -m pytest tests/test_context_language.py -q    # 16 tests
python -m pytest tests -q                             # full suite
```

Covered: detection (4 languages + romanised + unsupported script), morning/afternoon/evening/late
night, holiday priority, weather available/unavailable, greeting without location, greeting API,
stored greeting + state privacy, Hindi shortlist, English switch-back with state preserved,
explicit language selection, localised refusal.
