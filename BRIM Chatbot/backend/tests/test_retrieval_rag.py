import io
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService, GROUNDED_REFUSAL_MESSAGE

client = TestClient(app)

@pytest.fixture
def test_user():
    email = f"rag_tester_{uuid.uuid4().hex[:6]}@example.com"
    signup_res = client.post("/api/auth/signup", json={
        "name": "RAG Test User",
        "email": email,
        "password": "Password123!"
    })
    token = signup_res.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def real_estate_bot(test_user):
    # 1. Create project
    proj_res = client.post("/api/projects", json={
        "name": f"Luxury Real Estate {uuid.uuid4().hex[:4]}",
        "industry": "Real Estate"
    }, headers=test_user)
    proj_id = proj_res.json()["id"]

    # 2. Create bot
    bot_res = client.post("/api/bots", json={
        "project_id": proj_id,
        "name": "Skyline Realty Advisor",
        "welcome_message": "Welcome to Skyline Realty!"
    }, headers=test_user)
    bot_id = bot_res.json()["id"]

    # 3. Add rich knowledge base document
    knowledge_doc = (
        "Skyline Heights offers luxury 3 BHK and 4 BHK apartments in Gota, Ahmedabad. "
        "The starting price for a 3 BHK is 85 Lakhs INR, and 4 BHK units start at 1.45 Crores INR. "
        "Amenities include a rooftop infinity pool, 24/7 concierge, smart home automation, and dedicated EV charging stations. "
        "Site visits can be booked between 10:00 AM and 6:00 PM on weekdays."
    )
    files = {
        "file": ("skyline_brochure.txt", io.BytesIO(knowledge_doc.encode("utf-8")), "text/plain")
    }
    client.post(
        f"/api/bots/{bot_id}/knowledge/upload",
        files=files,
        headers=test_user
    )

    # 4. Add custom business instruction
    client.post(
        f"/api/bots/{bot_id}/knowledge/instruction",
        json={
            "name": "Booking Policy",
            "instructions": "All apartment bookings require an initial 10% token deposit. Down payments are payable within 30 days.",
            "tone": "Professional and courteous",
            "restrictions": "Do not negotiate fixed price quotes without approval from the sales director."
        },
        headers=test_user
    )

    return {"id": bot_id, "slug": bot_res.json()["shareable_slug"]}

@pytest.fixture
def healthcare_bot(test_user):
    # Create medical bot for bot-isolation test
    proj_res = client.post("/api/projects", json={
        "name": f"Dental Care Clinic {uuid.uuid4().hex[:4]}",
        "industry": "Healthcare"
    }, headers=test_user)
    proj_id = proj_res.json()["id"]

    bot_res = client.post("/api/bots", json={
        "project_id": proj_id,
        "name": "Smile Dental Bot",
        "welcome_message": "Welcome to Smile Dental!"
    }, headers=test_user)
    bot_id = bot_res.json()["id"]

    clinic_doc = (
        "Smile Dental Clinic is open Monday through Saturday from 9 AM to 7 PM. "
        "We offer teeth cleaning for $80, dental implants starting at $1200, and emergency tooth extractions. "
        "Dr. Sarah Jenkins is our lead orthodontist."
    )
    files = {
        "file": ("clinic_services.txt", io.BytesIO(clinic_doc.encode("utf-8")), "text/plain")
    }
    client.post(
        f"/api/bots/{bot_id}/knowledge/upload",
        files=files,
        headers=test_user
    )

    return {"id": bot_id, "slug": bot_res.json()["shareable_slug"]}

@pytest.fixture
def empty_bot(test_user):
    proj_res = client.post("/api/projects", json={
        "name": f"Empty Knowledge Project {uuid.uuid4().hex[:4]}",
        "industry": "E-commerce"
    }, headers=test_user)
    proj_id = proj_res.json()["id"]

    bot_res = client.post("/api/bots", json={
        "project_id": proj_id,
        "name": "Empty Knowledge Bot",
        "welcome_message": "Hello!"
    }, headers=test_user)
    return {"id": bot_res.json()["id"], "slug": bot_res.json()["shareable_slug"]}


# ==========================================
# 1. Relevant Retrieval & Grounded Answer Test
# ==========================================
def test_relevant_retrieval_and_grounded_answer(test_user, real_estate_bot):
    """
    Test that asking about 3 BHK prices in Skyline Heights retrieves the skyline_brochure source
    and responds with accurate factual details.
    """
    response = client.post(
        f"/api/bots/{real_estate_bot['id']}/chat",
        json={"message": "What is the starting price for 3 BHK apartments in Skyline Heights?"},
        headers=test_user
    )
    assert response.status_code == 200
    data = response.json()

    assert data["bot_id"] == real_estate_bot["id"]
    assert len(data["sources"]) >= 1
    
    # Verify source citation metadata
    top_source = data["sources"][0]
    assert "skyline_brochure.txt" in top_source["source_name"]
    assert top_source["similarity_score"] > 0.05

    # Verify grounded content in reply
    reply = data["reply"]
    assert "85 Lakhs" in reply or "Skyline Heights" in reply or "3 BHK" in reply


# ==========================================
# 2. Strict Bot-Level Multi-Tenant Isolation
# ==========================================
def test_bot_isolation_enforcement(test_user, real_estate_bot, healthcare_bot):
    """
    Test that real estate questions asked to the Healthcare Bot DO NOT leak or retrieve
    real estate chunks, and conversely dental queries to real estate bot return no dental data.
    """
    # Ask healthcare bot about real estate
    res_health = client.post(
        f"/api/bots/{healthcare_bot['id']}/chat",
        json={"message": "What is the price of a 3 BHK luxury flat?"},
        headers=test_user
    )
    assert res_health.status_code == 200
    data_health = res_health.json()

    # None of the sources should be from the real estate bot
    for src in data_health["sources"]:
        assert src["source_name"] != "skyline_brochure.txt"

    # Ask real estate bot about dental implants
    res_re = client.post(
        f"/api/bots/{real_estate_bot['id']}/chat",
        json={"message": "How much does a dental implant cost with Dr. Sarah Jenkins?"},
        headers=test_user
    )
    assert res_re.status_code == 200
    data_re = res_re.json()

    for src in data_re["sources"]:
        assert src["source_name"] != "clinic_services.txt"


# ==========================================
# 3. Empty Knowledge Base Handling
# ==========================================
def test_empty_knowledge_base(test_user, empty_bot):
    """
    Test that querying a bot with no uploaded sources returns a grounded refusal
    and advises contacting human support without crashing.
    """
    response = client.post(
        f"/api/bots/{empty_bot['id']}/chat",
        json={"message": "What are your operating hours?"},
        headers=test_user
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 0
    assert "do not have enough information" in data["reply"].lower()


# ==========================================
# 4. Missing Information / Hallucination Refusal
# ==========================================
def test_missing_information_refusal(test_user, real_estate_bot):
    """
    Test that asking for ungrounded / missing information (e.g. rocket warranty or Martian taxes)
    triggers refusal instead of hallucinating facts.
    """
    response = client.post(
        f"/api/bots/{real_estate_bot['id']}/chat",
        json={"message": "What is your warranty policy on interstellar starships to Pluto?"},
        headers=test_user
    )
    assert response.status_code == 200
    data = response.json()
    assert "do not have enough information" in data["reply"].lower() or "contact" in data["reply"].lower()


# ==========================================
# 5. Public Endpoint Demonstration
# ==========================================
def test_public_chat_endpoint(real_estate_bot):
    """
    Test the unauthenticated public chat endpoint via shareable slug.
    """
    response = client.post(
        f"/api/public/bots/{real_estate_bot['slug']}/chat",
        json={"message": "What are the luxury 3 BHK amenities and site visit timings for Skyline Heights?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["bot_name"] == "Skyline Realty Advisor"
    assert len(data["sources"]) >= 1
    assert "Skyline" in data["reply"] or "visit" in data["reply"].lower() or "pool" in data["reply"].lower() or "3 BHK" in data["reply"]


# ==========================================
# 6. Embedding & Vector Math Verification
# ==========================================
def test_embedding_service_cosine_similarity():
    """
    Verify mathematical correctness of cosine similarity and embedding dimension.
    """
    vec_a = EmbeddingService.get_embedding("Luxury real estate apartment in Gota")
    vec_b = EmbeddingService.get_embedding("3 BHK flat residential property in Gota")
    vec_c = EmbeddingService.get_embedding("Quantum physics particle accelerator decay")

    assert len(vec_a) == 1536
    assert len(vec_b) == 1536
    assert len(vec_c) == 1536

    sim_related = EmbeddingService.cosine_similarity(vec_a, vec_b)
    sim_unrelated = EmbeddingService.cosine_similarity(vec_a, vec_c)

    assert sim_related > sim_unrelated
    assert sim_related > 0.10
