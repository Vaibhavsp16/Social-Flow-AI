# BRIM AI — Verified Demo Questions

Every question below was sent through the real pipeline (retrieval → answer → citations) against a
bot created with that knowledge base. **All 42 returned a grounded answer with citations** — each
one is marked ✓.

Pick a knowledge base in **Create Bot → Step 2**, then ask these in the chat.

> **Why the exact wording matters:** with no OpenAI credits, embeddings use the local projection,
> which matches on **vocabulary**. Questions that use words appearing in the document retrieve
> reliably; heavily paraphrased questions may refuse. Adding credits makes paraphrase work too —
> no code change needed. Two phrasings that failed before reworking are noted at the end so you
> don't use them by accident.

---

## 1. 🏢 Prycoons Real Estate — "Prycoons Real Estate Official Guide"

Source: `Prycoons_Real_Estate_Guide.txt` · 4 chunks · Real Estate industry

| Question | Expected in answer |
|---|---|
| ✓ What are the 3 BHK prices and amenities at Sunset Palms? | ₹1.85 Cr, rooftop infinity pool, gymnasium |
| ✓ What is the configuration and carpet area of the apartments at Sunset Palms? | 3 BHK 2,150–2,400 sq ft, 4 BHK 3,100–3,450 sq ft |
| ✓ What is the price of The Heights penthouses? | ₹3.50 Cr up to ₹5.20 Cr |
| ✓ What is the booking token amount for a 3 BHK and a 4 BHK? | ₹5,00,000 / ₹10,00,000 |
| ✓ How much down payment is required and by when? | 20% within 30 days of booking |
| ✓ What is the possession date for Sunset Palms? | December 2026 |
| ✓ What amenities does The Heights offer? | Private splash pool, personal elevator, 3 parking slots |
| ✓ What is the stamp duty and registration fee? | 5% stamp duty + 1% registration |
| ✓ What are the visiting hours at the sales office? | Mon–Sun, 10:00 AM to 7:00 PM |
| ✓ What is the phone number and email for Prycoons? | +91 (079) 4920-8800 / contact@prycoons.com |
| ✓ Which banks offer pre-approved home loans and at what interest rate? | HDFC, ICICI, SBI at 8.4% p.a. |
| ✓ Where is the sales office located? | 402 Prycoons Towers, Ambli-Bopal Road, Ahmedabad 380058 |
| ✓ Do site visits include pick-up? | Complimentary chauffeur pick-up |
| ✓ Is Sunset Palms RERA approved? | PR/GJ/AHMEDABAD/2024/00481 |

**Also verified:** *"What information do you have about this business?"* — the broad overview
question from the brief. It is answered from the guide rather than refused.

---

## 2. 🏥 Apex Healthcare — "Apex Healthcare Wellness Clinic Guide"

Source: `Apex_Healthcare_Clinic_Guide.txt` · 3 chunks · Healthcare industry

| Question | Expected in answer |
|---|---|
| ✓ What specialties does Apex Healthcare offer? | Cardiology, orthopedics, pediatrics, general medicine |
| ✓ Who is the cardiologist and what are the consultation timings? | Dr. Rajesh Verma, Mon/Wed/Fri 9:00 AM–1:00 PM |
| ✓ What is the general OPD consultation fee? | ₹600 |
| ✓ What is the super specialist consultation fee? | ₹1,200 |
| ✓ Is a follow-up visit free? | Free within 7 days |
| ✓ What diagnostic facilities are available? | MRI, CT scan, X-ray, Doppler, pathology lab |
| ✓ How much does a full-body executive health checkup cost? | From ₹3,499 |
| ✓ What are the emergency room timings? | Open 24/7 |
| ✓ What is the ambulance phone number? | 1800-419-9111 |
| ✓ Which insurance providers are accepted? | Star Health, Care Health, HDFC ERGO, ICICI Lombard, Max Bupa |
| ✓ Who is the orthopedics doctor and what are their timings? | Dr. Meera Shenoy, Tue/Thu/Sat 2:00–6:00 PM |
| ✓ Who handles pediatrics and what are the hours? | Dr. Anand Patel, daily 10:00 AM–4:00 PM |
| ✓ What is the appointment booking phone number? | +91 (022) 6789-4321 |
| ✓ Do you have MRI and CT scan facilities? | 1.5 Tesla MRI, 64-slice CT scan |

---

## 3. ☁️ CloudScale SaaS — "CloudScale SaaS Platform Documentation"

Source: `CloudScale_SaaS_Platform_Docs.txt` · 3 chunks · Technology & SaaS industry

| Question | Expected in answer |
|---|---|
| ✓ What are the pricing plans for CloudScale? | Starter $49, Growth $199, Enterprise from $899 |
| ✓ What is included in the Starter plan? | 500k events, 3 seats, 24-hour SLA, 14-day retention |
| ✓ What is the event limit and data retention in the Growth plan? | 5M events, 90-day retention |
| ✓ What does the Enterprise plan include and what does it cost? | Custom from $899/mo, 99.99% uptime, unlimited events |
| ✓ What are the API rate limits? | 2,000/min Growth, 10,000/min Enterprise |
| ✓ What SDK support and integrations are available? | Python, Node.js, Go, Java, React, iOS, Android |
| ✓ What security certifications does CloudScale have? | SOC 2 Type II, GDPR compliant |
| ✓ Is there SSO support? | SAML 2.0 / Okta SSO |
| ✓ What is the uptime guarantee? | 99.99% with financial credits |
| ✓ What is the support email for enterprise customers? | support@cloudscale.io |
| ✓ What is the support SLA for priority chat? | 4-hour SLA (Growth) |
| ✓ How many team member seats are in each plan? | 3 / 15 / unlimited |
| ✓ Is data encrypted at rest and in transit? | AES-256 at rest, TLS 1.3 in transit |
| ✓ Is there a HIPAA BAA available? | Yes, on request |

---

## Useful negative test (proves it doesn't hallucinate)

Ask any bot something **not** in its document:

> "What is the warranty policy on interstellar starships to Pluto?"

Expected: a polite refusal — *"I do not have enough information in my knowledge base to answer this
question accurately…"* — with **no** citation chips. This is the single best moment to show a
sceptical audience that answers are grounded, not invented.

---

## Phrasings that did NOT work (and what to say instead)

These use vocabulary absent from the document, so retrieval found nothing:

| Don't ask | Ask instead |
|---|---|
| "What imaging equipment do you have?" | "Do you have MRI and CT scan facilities?" |
| "Which programming languages and SDKs are supported?" | "What SDK support and integrations are available?" |

This is expected behaviour for lexical retrieval — it is the system correctly refusing rather than
guessing. Adding OpenAI credits removes this limitation.
