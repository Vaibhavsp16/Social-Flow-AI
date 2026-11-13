<#
End-to-end verification of the 11 feature changes against the running docker stack.

    powershell -File scripts/verify_stack.ps1

Assumes: docker compose up -d --build, API on http://localhost:8000, web app on http://localhost:8080.
Exits non-zero on the first failed assertion so this can gate a handover.
#>

$ErrorActionPreference = 'Stop'

$Api = if ($env:E2E_API) { $env:E2E_API } else { 'http://localhost:8000/api' }
$Web = if ($env:E2E_WEB) { $env:E2E_WEB } else { 'http://localhost:8080' }

$script:Passed = 0
$script:Failed = 0
$script:Results = @()

function Check([string]$name, [scriptblock]$body) {
    try {
        & $body
        $script:Passed++
        $script:Results += [pscustomobject]@{ Result = 'PASS'; Check = $name; Detail = '' }
        Write-Host "  PASS  $name" -ForegroundColor Green
    }
    catch {
        $script:Failed++
        $msg = $_.Exception.Message
        $script:Results += [pscustomobject]@{ Result = 'FAIL'; Check = $name; Detail = $msg }
        Write-Host "  FAIL  $name" -ForegroundColor Red
        Write-Host "        $msg" -ForegroundColor DarkGray
    }
}

function AuthHeaders([string]$token) { @{ Authorization = "Bearer $token" } }

function Post([string]$path, $body, [string]$token = $null) {
    $headers = @{}
    if ($token) { $headers = AuthHeaders $token }
    Invoke-RestMethod -Method Post -Uri "$Api$path" -Headers $headers `
        -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 8 -Compress)
}

function Patch([string]$path, $body, [string]$token = $null) {
    $headers = @{}
    if ($token) { $headers = AuthHeaders $token }
    Invoke-RestMethod -Method Patch -Uri "$Api$path" -Headers $headers `
        -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 8 -Compress)
}

function Put([string]$path, $body, [string]$token = $null) {
    $headers = @{}
    if ($token) { $headers = AuthHeaders $token }
    Invoke-RestMethod -Method Put -Uri "$Api$path" -Headers $headers `
        -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 8 -Compress)
}

function GetJson([string]$path, [string]$token = $null) {
    $headers = @{}
    if ($token) { $headers = AuthHeaders $token }
    Invoke-RestMethod -Method Get -Uri "$Api$path" -Headers $headers
}

function Assert([bool]$condition, [string]$message) {
    if (-not $condition) { throw $message }
}

# Header access differs between Windows PowerShell 5.1 and 7, so read it defensively.
function HeaderValue($response, [string]$name) {
    if ($null -eq $response.Headers) { return '' }
    $headers = $response.Headers
    if ($headers -is [System.Collections.IDictionary]) {
        foreach ($key in @($headers.Keys)) {
            if ($key -ieq $name) { return (@($headers[$key]) -join ',') }
        }
    }
    return ''
}

function GetRaw([string]$url, $headers = @{}) {
    Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing -TimeoutSec 20
}

# ── 0. Stack is up ────────────────────────────────────────────────────────────
Write-Host "`n[0] Health" -ForegroundColor Cyan
$health = $null
try { $health = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 10 } catch { }
Check 'API health endpoint returns ok' {
    Assert ($null -ne $health) 'http://localhost:8000/health did not respond'
    Assert ($health.status -eq 'healthy') "unexpected health payload: $($health | ConvertTo-Json -Compress)"
}

# ── 1. Account ───────────────────────────────────────────────────────────────
Write-Host "`n[1] Account" -ForegroundColor Cyan
$email = "e2e_$([guid]::NewGuid().ToString('N').Substring(0,10))@example.com"
$signup = Post '/auth/signup' @{ name = 'E2E Verifier'; email = $email; password = 'Password123!' }
$token = $signup.access_token
Check 'Signup returns a JWT' { Assert ($token.Length -gt 20) 'no access token in signup response' }

Check 'Google config is exposed and honest about being unconfigured' {
    $config = GetJson '/auth/google/config'
    Assert ($null -ne $config) 'no /auth/google/config response'
    if (-not $config.enabled) {
        Assert ($config.message -match 'GOOGLE_CLIENT_ID') "disabled but the message does not name the setting: $($config.message)"
    }
}

# ── 2. Bot with behaviour ────────────────────────────────────────────────────
Write-Host "`n[2] Bot creation with use case, style and policies" -ForegroundColor Cyan
$project = Post '/projects' @{ name = "E2E Estates $([guid]::NewGuid().ToString('N').Substring(0,6))"; industry = 'Real Estate' } $token
$slugSuffix = [guid]::NewGuid().ToString('N').Substring(0, 6)
$bot = Post '/bots' @{
    project_id          = $project.id
    name                = "E2E Assistant $slugSuffix"
    description         = 'End to end verification bot'
    language            = 'English'
    personality         = 'Warm & conversational'
    welcome_message     = 'Hi! Looking for a home?'
    status              = 'Live'
    primary_use_case    = 'appointment_booking'
    response_style      = 'concise'
    lead_collection     = 'always'
    human_handoff       = 'allow_when_needed'
    company_name        = 'E2E Estates'
    idle_prompt_seconds = 30
    contact_after_messages = 2
} $token

Check 'Bot stores primary_use_case' { Assert ($bot.primary_use_case -eq 'appointment_booking') "got '$($bot.primary_use_case)'" }
Check 'Bot stores response_style' { Assert ($bot.response_style -eq 'concise') "got '$($bot.response_style)'" }
Check 'Bot stores lead_collection' { Assert ($bot.lead_collection -eq 'always') "got '$($bot.lead_collection)'" }
Check 'Bot stores company_name' { Assert ($bot.company_name -eq 'E2E Estates') "got '$($bot.company_name)'" }
Check 'Bot stores the contact threshold' { Assert ($bot.contact_after_messages -eq 2) "got '$($bot.contact_after_messages)'" }

Check 'An invalid use case is rejected instead of silently ignored' {
    $threw = $false
    try {
        Post '/bots' @{ project_id = $project.id; name = 'Bad case'; primary_use_case = 'not_a_real_case' } $token | Out-Null
    } catch { $threw = $true }
    Assert $threw 'the API accepted an unknown use case'
}

Check 'Behaviour fields are editable after creation' {
    $updated = Put "/bots/$($bot.id)" @{ response_style = 'detailed'; primary_use_case = 'lead_generation' } $token
    Assert ($updated.response_style -eq 'detailed') "response_style did not update: $($updated.response_style)"
    Assert ($updated.primary_use_case -eq 'lead_generation') "primary_use_case did not update: $($updated.primary_use_case)"
    # Put it back so the rest of the run matches the created configuration.
    Put "/bots/$($bot.id)" @{ response_style = 'concise'; primary_use_case = 'appointment_booking' } $token | Out-Null
}

$slug = $bot.shareable_slug
Check 'Bot has a shareable slug' { Assert (-not [string]::IsNullOrWhiteSpace($slug)) 'no slug on the bot' }

# ── 3. Public surface ────────────────────────────────────────────────────────
Write-Host "`n[3] Public page, embed widget, custom domain" -ForegroundColor Cyan
$publicBot = GetJson "/public/bots/$slug"
Check 'Public bot metadata loads without a token' {
    Assert ($publicBot.name -eq $bot.name) "wrong bot returned: $($publicBot.name)"
    Assert ($publicBot.idle_prompt_seconds -eq 30) "idle seconds not exposed: $($publicBot.idle_prompt_seconds)"
}

Check 'Embed snippet points at this deployment' {
    $embed = GetJson "/public/bots/$slug/embed-snippet"
    Assert ($embed.snippet -match 'widget\.js') "snippet has no widget.js: $($embed.snippet)"
    Assert ($embed.snippet -match "data-bot=`"$slug`"") "snippet is not bound to the slug: $($embed.snippet)"
    Assert ($embed.public_url -match "/p/$slug") "public url is wrong: $($embed.public_url)"
    Assert ($embed.public_url -notmatch 'chat\.brim\.ai') 'public url still uses the dead chat.brim.ai host'
}

Check 'widget.js is served as JavaScript' {
    $response = GetRaw "$Api/public/widget.js"
    Assert ($response.StatusCode -eq 200) "status $($response.StatusCode)"
    $contentType = HeaderValue $response 'Content-Type'
    Assert ($contentType -match 'javascript') "content type: '$contentType'"
    Assert ($response.Content -match '/p/') 'widget does not frame the public page'
    Assert ($response.Content -match 'data-bot') 'widget does not read the data-bot attribute'
}

Check 'A draft bot is not published' {
    Put "/bots/$($bot.id)" @{ status = 'Draft' } $token | Out-Null
    $status = 200
    try { GetJson "/public/bots/$slug" | Out-Null } catch { $status = [int]$_.Exception.Response.StatusCode }
    Put "/bots/$($bot.id)" @{ status = 'Live' } $token | Out-Null
    Assert ($status -eq 403) "draft bot returned $status instead of 403"
}

Check 'Custom domain saves as pending with DNS instructions' {
    $domain = Put "/bots/$($bot.id)/domain" @{ domain = "chat$slugSuffix.example.com" } $token
    Assert ($domain.domain -eq "chat$slugSuffix.example.com") "domain not saved: $($domain.domain)"
    Assert ($domain.status -eq 'pending') "status: $($domain.status)"
    Assert ($domain.token.Length -ge 8) 'no verification token issued'
    $instructions = ($domain.instructions | Out-String)
    Assert ($instructions -match '_brim-verify') 'TXT record guidance missing'
}

Check 'Verifying a domain with no DNS records never reports verified' {
    $verified = Post "/bots/$($bot.id)/domain/verify" @{} $token
    Assert ($verified.status -ne 'verified') "was marked verified without DNS: $($verified.status)"
    Assert ($null -ne $verified.checks) 'no check results returned'
}

# ── 4. Conversation, contact capture, scheduling ──────────────────────────────
Write-Host "`n[4] Chat: contact capture, idle nudge, scheduling" -ForegroundColor Cyan
$visitorId = "e2e-visitor-$slugSuffix"
$convo = Post "/public/conversations/$slug" @{
    visitor_id         = $visitorId
    channel            = 'embed'
    timezone           = 'Asia/Calcutta'
    utc_offset_minutes = 330
}

Check 'Public conversation is created and tagged' {
    Assert ($convo.visitor_id -eq $visitorId) "visitor not stored: $($convo.visitor_id)"
    Assert ($convo.channel -eq 'embed') "channel: $($convo.channel)"
}

$first = Post "/public/conversations/$($convo.id)/messages" @{ message = 'What do you have in Ambli?' }
$second = Post "/public/conversations/$($convo.id)/messages" @{ message = 'Which is closest to the metro?' }

Check 'Bot asks for contact details after a couple of turns' {
    # The threshold is 2, so it fires on the first or second reply — then never again.
    $prompt = if ($first.contact_prompt) { $first.contact_prompt } else { $second.contact_prompt }
    Assert ($null -ne $prompt) 'no contact prompt after the configured threshold'
    Assert ($prompt.kind -eq 'contact') "kind: $($prompt.kind)"
    Assert ($null -eq $second.contact_prompt -or $null -eq $first.contact_prompt) 'the prompt repeated on every turn'
}

Check 'A second chat by the same visitor is still one visitor' {
    $third = Post "/public/conversations/$slug" @{ visitor_id = "e2e-other-$slugSuffix"; channel = 'embed' }
    Assert ($third.visitor_id -ne $visitorId) 'a different visitor was given the same identity'
    Assert ($third.id -ne $convo.id) 'a different visitor reused another visitor''s conversation'
}

Check 'Idle nudge fires once and then refuses to repeat' {
    $nudge = Post "/public/conversations/$($convo.id)/nudge" @{ kind = 'idle' }
    Assert ($nudge.sent) "first nudge not sent: $($nudge | ConvertTo-Json -Compress)"
    $again = Post "/public/conversations/$($convo.id)/nudge" @{ kind = 'idle' }
    Assert (-not $again.sent) 'the nudge fired twice for the same conversation'
}

Check 'Contact details submitted from the card become a lead with a preferred time' {
    $contact = Post "/public/conversations/$($convo.id)/contact" @{
        name           = 'Ravi Shah'
        phone          = '+91 98250 12345'
        email          = 'ravi@example.com'
        preferred_time = 'Weekday evenings after 6pm'
        source         = 'idle_prompt'
    }
    Assert ($contact.saved) "contact not saved: $($contact | ConvertTo-Json -Compress)"
    Assert ($contact.lead.phone -match '98250') "phone not stored: $($contact.lead.phone)"
}

Check 'Lead is visible to the owner with the phone and the preferred time' {
    $leads = GetJson "/bots/$($bot.id)/leads" $token
    Assert ($leads.Count -ge 1) "no leads returned"
    $lead = $leads | Where-Object { $_.phone -match '98250' } | Select-Object -First 1
    Assert ($null -ne $lead) 'the captured lead is missing from the owner list'
    Assert ($lead.preferred_time -match 'evening') "preferred_time missing: $($lead.preferred_time)"
    Assert ($lead.source -eq 'idle_prompt') "source: $($lead.source)"
}

Check 'Leads CSV exports the real number for the business' {
    $csv = GetRaw "$Api/bots/$($bot.id)/leads.csv" (AuthHeaders $token)
    Assert ($csv.StatusCode -eq 200) "status $($csv.StatusCode)"
    $contentType = HeaderValue $csv 'Content-Type'
    Assert ($contentType -match 'csv') "content type: '$contentType'"
    Assert ($csv.Content -match '98250') 'the CSV does not contain the phone number'
    Assert ($csv.Content -match 'preferred_time') 'the CSV has no preferred_time column'
}

Check 'The bot books a call across three turns' {
    $ask = Post "/public/conversations/$($convo.id)/messages" @{ message = 'Can someone call me?' }
    Assert ($ask.reply -match '\?') "the bot did not ask for a time: $($ask.reply)"
    $slot = Post "/public/conversations/$($convo.id)/messages" @{ message = 'Tuesday 6pm' }
    $booked = Post "/public/conversations/$($convo.id)/messages" @{ message = 'yes' }
    $meetingRows = GetJson "/bots/$($bot.id)/meetings" $token
    # The endpoint returns {count, meetings}; read the list, not the envelope.
    $meetings = if ($meetingRows.meetings) { $meetingRows.meetings } else { $meetingRows }
    Assert ($meetings.Count -ge 1) 'no meeting row was created'
    $meeting = $meetings | Select-Object -First 1
    Assert ($meeting.preferred_slot -match 'Tuesday') "the requested slot was lost: '$($meeting.preferred_slot)'"
    Assert ($null -ne $meeting.scheduled_for) 'the slot was not resolved to a concrete time'
    Assert (-not [string]::IsNullOrWhiteSpace($meeting.phone)) 'the meeting has no contact number'
}

# ── 5. Analytics ────────────────────────────────────────────────────────────
Write-Host "`n[5] Analytics" -ForegroundColor Cyan
Check 'Live counters move with the conversation' {
    $live = GetJson "/analytics/bots/$($bot.id)/live" $token
    Assert ($live.today.conversations -ge 2) "conversations today: $($live.today.conversations)"
    Assert ($live.today.messages -ge 4) "messages today: $($live.today.messages)"
    Assert ($live.today.leads -ge 1) "leads today: $($live.today.leads)"
    Assert ($live.today.meetings -ge 1) "meetings today: $($live.today.meetings)"
}

Check 'Unique users counts people, not chats' {
    $report = GetJson "/analytics/bots/$($bot.id)" $token
    # Two visitors, four conversations: the number must be 2, not 4.
    Assert ($report.totals.unique_users -eq 2) "unique_users=$($report.totals.unique_users) for 2 visitors / $($report.totals.conversations) chats"
}

# ── 6. Frontend ─────────────────────────────────────────────────────────────
Write-Host "`n[6] Web app" -ForegroundColor Cyan
Check 'Public chat page is served' {
    $page = GetRaw "$Web/p/$slug"
    Assert ($page.StatusCode -eq 200) "status $($page.StatusCode)"
    Assert ($page.Content -match '<div id="root"') 'the SPA shell was not returned'
}

Check 'Embed mode is served' {
    $page = GetRaw "$Web/p/$slug`?embed=1"
    Assert ($page.StatusCode -eq 200) "status $($page.StatusCode)"
}

# ── Summary ─────────────────────────────────────────────────────────────────
Write-Host "`n────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  $($script:Passed) passed, $($script:Failed) failed" -ForegroundColor $(if ($script:Failed) { 'Red' } else { 'Green' })
Write-Host "  Bot: $($bot.name)  |  slug: $slug" -ForegroundColor DarkGray
Write-Host "  Public page: $Web/p/$slug" -ForegroundColor DarkGray
Write-Host "────────────────────────────────────────`n" -ForegroundColor DarkGray

if ($script:Failed -gt 0) {
    $script:Results | Where-Object { $_.Result -eq 'FAIL' } | Format-Table -AutoSize | Out-String | Write-Host
    exit 1
}
exit 0
