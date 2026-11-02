# Analytics, reporting and administration

Every figure is computed from rows in PostgreSQL. There is no synthetic traffic, no extrapolation
and no "sample" data in these views. If a window contains no conversations, the API returns
`has_data: false` and the UI shows **"No conversation data yet."**

## Metric definitions

| Metric | Definition |
|---|---|
| Total conversations | `conversations.started_at` inside the selected range |
| Unique users | distinct `conversations.session_id` in range (the identity a visitor has) |
| Total messages | `messages` belonging to conversations started in range |
| Leads | `leads.created_at` in range |
| Human handoffs | conversations whose status is `HANDOFF_REQUESTED` or `HANDED_OFF` |
| Resolved | conversation that produced a lead, or ended (`ENDED`) without a handoff |
| Resolution rate | resolved ÷ total conversations |
| Unresolved | total − resolved |
| Avg messages / conversation | messages ÷ conversations |
| Lead conversion | leads ÷ total conversations |
| Intent distribution | `conversations.intent` — buying / renting / browsing / other |
| Conversation volume | conversations and messages grouped by day |
| Frequently retrieved sources | `sources[].source_name` aggregated from assistant message metadata |
| Unanswered question | a user question whose next assistant reply is the canonical refusal, or that never received a reply |

Aggregates are computed per bot, and the platform view reuses the same code path with a wider bot
scope, so business and admin numbers cannot drift apart.

## Reports

`ReportingService.build()` returns a dict — title, columns, rows, summary, range, filters. CSV is
one renderer over that structure, and a PDF renderer can be added by consuming the same dict.

| Kind | Columns |
|---|---|
| `conversations` | id, bot, started_at, intent, status, messages, lead_captured, handoff, resolved |
| `leads` | id, created_at, bot, name, phone_masked, email_masked, preferred_contact, intent, location, budget_max, status |
| `bot_usage` | bot, status, conversations, unique_users, messages, leads, handoffs, resolution_rate |
| `intents` | intent, conversations, share_pct |
| `handoffs` | conversation_id, bot, started_at, status, last_message_at, messages |
| `unanswered` | conversation_id, bot, asked_at, reason, question |

CSV downloads are UTF-8 with a BOM (Excel-friendly) and are generated from the exact same rows the
JSON endpoint returns — asserted by `test_csv_matches_json_rows`.

## Administration

`users.role = 'ADMIN'` is the only difference between an admin and a business account. Every route
under `/api/admin` depends on `require_admin`; business accounts receive **403**, never a filtered
response.

Admin can view: overview metrics, users, projects, bots, conversations, leads and the activity feed.

Privacy rules applied in the admin console:

- Password hashes are never serialised (the schema never includes them).
- End-customer phone and email are masked (`****0011`, `*****ple.com`). Platform account emails
  are shown because identifying an account is the point of the console.
- Activity metadata stores ids, names and counts only — no emails, phone numbers or message text.

## Activity events

Recorded on: `user_signup`, `user_login`, `project_created`, `bot_created`, `bot_published`,
`conversation_started`, `knowledge_added`, `lead_captured`, `handoff_requested`.

Events join the caller's transaction, so an event exists only if the action it describes committed.
Logging failures are swallowed — analytics can never break signup or a chat turn.

## Endpoints

```
GET  /api/analytics/overview?start&end
GET  /api/analytics/bots/{id}?start&end
GET  /api/reports/{kind}?start&end&bot_id&format=json|csv
GET  /api/admin/overview?start&end
GET  /api/admin/{users|projects|bots|conversations|leads|activity}?limit&offset
GET  /api/admin/reports/{kind}?format=json|csv
```

## Admin account

```bash
cd backend
python scripts/seed_admin.py                  # admin@brim.ai / Admin@12345
python scripts/seed_admin.py you@brim.ai pw   # custom
```

Change the password before any real deployment; it is a demo credential like the `demo@brim.ai`
business account.

## Tests

`tests/test_analytics_admin.py` — 16 tests: metrics vs SQL counts, intent distribution, resolution
maths, empty-bot behaviour, date-range exclusion, cross-tenant 404, scoped reports, admin 403 for
business users, admin platform visibility, masked lead PII, activity coverage, and CSV/JSON parity
for all six report kinds.
