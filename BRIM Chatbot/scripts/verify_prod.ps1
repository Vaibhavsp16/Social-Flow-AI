<#
Production verification against the deployed API.

    pwsh -File scripts/verify_prod.ps1

Read-mostly: it logs in with the seeded demo account, creates ONE temporary bot to exercise the
requested behaviour, and deletes it at the end. Nothing else is created.
#>

$ErrorActionPreference = 'Stop'
$Api = if ($env:E2E_API) { $env:E2E_API } else { 'https://brim-api-dxgh.onrender.com/api' }
$Web = if ($env:E2E_WEB) { $env:E2E_WEB } else { 'https://social-flow-ai-frontend.vercel.app' }

$script:pass = 0; $script:fail = 0
function Check($name, [scriptblock]$body) {
    try { & $body; Write-Host "PASS  $name" -ForegroundColor Green; $script:pass++ }
    catch { Write-Host "FAIL  $name :: $($_.Exception.Message)" -ForegroundColor Red; $script:fail++ }
}

function Login {
    $b = @{ email = 'vaibhav@example.com'; password = 'password123' } | ConvertTo-Json
    Invoke-RestMethod -Uri "$Api/auth/login" -Method Post -ContentType 'application/json' -Body $b -TimeoutSec 90
}

function Say($id, $message) {
    Invoke-RestMethod -Uri "$Api/public/conversations/$id/messages" -Method Post `
        -ContentType 'application/json' -Body (@{ message = $message } | ConvertTo-Json) -TimeoutSec 120
}

$token = $null; $botId = $null; $slug = $null
try {
    $login = Login
    $token = $login.access_token
    $H = @{ Authorization = "Bearer $token" }

    $existing = Invoke-RestMethod -Uri "$Api/bots" -Headers $H -TimeoutSec 90
    $projectId = $existing[0].project_id

    Write-Host "`n[n] Creating a temporary bot on production" -ForegroundColor Cyan
    $suffix = -join ((1..6) | ForEach-Object { 'abcdefghijklmnopqrstuvwxyz0123456789'[(Get-Random -Max 36)] })
    $slug = "prod-check-$suffix"
    $payload = @{
        project_id      = $projectId
        name            = "Prod Check $suffix"
        description     = 'Temporary verification bot'
        language        = 'English'
        personality     = 'Friendly & professional'
        welcome_message = 'Hi! How can I help you today?'
        status          = 'Live'
        primary_use_case = 'appointment_booking'
        response_style   = 'concise'
        lead_collection  = 'always'
        human_handoff    = 'allow_when_needed'
        company_name     = 'Prod Check Estates'
    } | ConvertTo-Json
    $bot = Invoke-RestMethod -Uri "$Api/bots" -Method Post -Headers $H -ContentType 'application/json' -Body $payload -TimeoutSec 120
    $botId = $bot.id
    $slug = $bot.shareable_slug

    Check '10/11 behaviour fields persist on production' {
        $b = Invoke-RestMethod -Uri "$Api/bots/$botId" -Headers $H -TimeoutSec 60
        if ($b.primary_use_case -ne 'appointment_booking') { throw "use case = $($b.primary_use_case)" }
        if ($b.response_style -ne 'concise') { throw "style = $($b.response_style)" }
        if ($b.lead_collection -ne 'always') { throw "lead = $($b.lead_collection)" }
        if ($b.company_name -ne 'Prod Check Estates') { throw "company = $($b.company_name)" }
    }

    Check '3 public bot metadata loads without a token' {
        $p = Invoke-RestMethod -Uri "$Api/public/bots/$slug" -TimeoutSec 60
        if ($p.name -ne "Prod Check $suffix") { throw "name = $($p.name)" }
    }

    Check '5 embed snippet points at this deployment, not chat.brim.ai' {
        $e = Invoke-RestMethod -Uri "$Api/public/bots/$slug/embed-snippet" -TimeoutSec 60
        if ($e.public_url -notmatch "/p/$slug") { throw "public_url = $($e.public_url)" }
        if ($e.public_url -match 'chat\.brim\.ai') { throw 'still points at chat.brim.ai' }
        if ($e.snippet -notmatch "data-bot=`"$slug`"") { throw 'snippet not bound to slug' }
    }

    $conv = Invoke-RestMethod -Uri "$Api/public/conversations/$slug" -Method Post -ContentType 'application/json' `
        -Body (@{ visitor_id = 'prod-visitor-1'; channel = 'web' } | ConvertTo-Json) -TimeoutSec 60

    Check '9 visitor id is stored and returned' {
        if ($conv.visitor_id -ne 'prod-visitor-1') { throw "visitor_id = $($conv.visitor_id)" }
    }

    $m1 = Say $conv.id 'What properties do you have in Ahmedabad?'
    $m2 = Say $conv.id 'I am looking at 3 BHK options'

    Check '7 contact prompt appears mid-conversation' {
        $prompt = if ($m1.contact_prompt) { $m1.contact_prompt } else { $m2.contact_prompt }
        if (-not $prompt) { throw 'no contact prompt after two turns' }
        if ($prompt.kind -ne 'contact') { throw "kind = $($prompt.kind)" }
    }

    Check '10/11 a knowledge miss still offers a use-case next step' {
        # This bot has no documents, so the reply is a miss; a booking bot must offer a visit.
        if (-not ($m1.reply -match 'site visit|call|team')) { throw "reply = $($m1.reply)" }
    }

    $n1 = Invoke-RestMethod -Uri "$Api/public/conversations/$($conv.id)/nudge" -Method Post `
        -ContentType 'application/json' -Body '{"kind":"idle"}' -TimeoutSec 60
    $n2 = Invoke-RestMethod -Uri "$Api/public/conversations/$($conv.id)/nudge" -Method Post `
        -ContentType 'application/json' -Body '{"kind":"idle"}' -TimeoutSec 60

    Check '6 idle nudge fires once and then stays quiet' {
        if (-not $n1.sent) { throw "first sent = $($n1.sent)" }
        if ($n2.sent) { throw 'nudge repeated' }
    }

    Check '7 contact details save with a preferred time' {
        $c = Invoke-RestMethod -Uri "$Api/public/conversations/$($conv.id)/contact" -Method Post -ContentType 'application/json' `
            -Body (@{ name = 'Prod Tester'; phone = '98250 12345'; preferred_time = 'Weekday evenings' } | ConvertTo-Json) -TimeoutSec 60
        if (-not $c.saved) { throw 'not saved' }
        if ($c.lead.phone -ne '9825012345') { throw "phone = $($c.lead.phone)" }
    }

    Check '7 leads CSV carries the real number and preferred time' {
        $resp = Invoke-WebRequest -Uri "$Api/bots/$botId/leads.csv" -Headers $H -TimeoutSec 60 -UseBasicParsing
        if ($resp.Content -notmatch '9825012345') { throw 'phone missing from CSV' }
        if ($resp.Content -notmatch 'preferred_time') { throw 'no preferred_time column' }
    }

    Check '8 a booking completes with slot and contact' {
        # The lead already has a number at this point, so the booking lands on the turn that
        # supplies the slot, not three turns later. Look across all three.
        $b1 = Say $conv.id 'Can I book a site visit?'
        $b2 = Say $conv.id 'Saturday 11am'
        $b3 = Say $conv.id 'Thanks, what happens next?'
        $meeting = $b1.meeting; if (-not $meeting) { $meeting = $b2.meeting }; if (-not $meeting) { $meeting = $b3.meeting }
        if (-not $meeting) { throw "no meeting returned; replies: $($b1.reply) | $($b2.reply) | $($b3.reply)" }
        if ($meeting.preferred_slot -ne 'Saturday 11am') { throw "slot = $($meeting.preferred_slot)" }
        if (-not ($b2.reply -match 'Saturday 11am')) { throw "reply = $($b2.reply)" }
    }

    Check '2 live analytics answers for this bot' {
        $live = Invoke-RestMethod -Uri "$Api/analytics/bots/$botId/live" -Headers $H -TimeoutSec 60
        if ($null -eq $live.today) { throw 'no today block' }
    }

    Check '4 custom domain saves as pending and never claims verified without DNS' {
        $d = Invoke-RestMethod -Uri "$Api/bots/$botId/domain" -Method Put -Headers $H -ContentType 'application/json' `
            -Body (@{ domain = "check-$suffix.example.com" } | ConvertTo-Json) -TimeoutSec 60
        if ($d.status -ne 'pending') { throw "status = $($d.status)" }
        if (-not $d.token) { throw 'no token' }
    }
}
finally {
    if ($botId -and $token) {
        try {
            Invoke-RestMethod -Uri "$Api/bots/$botId" -Method Delete -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 90 | Out-Null
            Write-Host "`nTemporary bot $botId deleted." -ForegroundColor Cyan
        } catch { Write-Host "`nCleanup failed for bot $botId :: $($_.Exception.Message)" -ForegroundColor Yellow }
    }
    Write-Host ("`n{0} passed, {1} failed`n" -f $script:pass, $script:fail)
    if ($script:fail -gt 0) { exit 1 }
}
