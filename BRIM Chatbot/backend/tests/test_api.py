import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_industries_list():
    response = client.get("/api/industries")
    assert response.status_code == 200
    industries = response.json()["industries"]
    assert "Real Estate" in industries
    assert "Technology & SaaS" in industries
    assert "Healthcare" in industries
    assert len(industries) == 16

def test_unauthenticated_requests_blocked():
    # Test that protected routes return 401 when no token is supplied
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json={"name": "Test", "industry": "Real Estate"}).status_code == 401
    assert client.get("/api/bots").status_code == 401
    assert client.post("/api/bots", json={"project_id": 1, "name": "Test"}).status_code == 401

def test_auth_and_project_bot_flow():
    # 1. Signup User A
    signup_payload = {
        "name": "Vaibhav Patel",
        "email": "vaibhav_flow@example.com",
        "password": "Password123!"
    }
    signup_res = client.post("/api/auth/signup", json=signup_payload)
    if signup_res.status_code == 400: # Already exists from previous run
        login_res = client.post("/api/auth/login", json={
            "email": "vaibhav_flow@example.com",
            "password": "Password123!"
        })
        token_a = login_res.json()["access_token"]
    else:
        assert signup_res.status_code == 201
        assert "access_token" in signup_res.json()
        assert signup_res.json()["user"]["email"] == "vaibhav_flow@example.com"
        token_a = signup_res.json()["access_token"]

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. /me endpoint verification
    me_res = client.get("/api/auth/me", headers=headers_a)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "vaibhav_flow@example.com"
    user_a_id = me_res.json()["id"]

    # 3. Create Project for User A with predefined industry
    project_payload = {
        "name": "Prycoons Real Estate Project",
        "industry": "Real Estate",
        "description": "Property discovery and customer enquiries."
    }
    project_res = client.post("/api/projects", json=project_payload, headers=headers_a)
    assert project_res.status_code == 201
    project_id = project_res.json()["id"]
    assert project_res.json()["industry"] == "Real Estate"
    assert project_res.json()["user_id"] == user_a_id

    # Test invalid industry rejection
    invalid_project_res = client.post("/api/projects", json={
        "name": "Invalid Project",
        "industry": "UnknownIndustryXYZ"
    }, headers=headers_a)
    assert invalid_project_res.status_code == 422

    # 4. List Projects for User A
    projects_list_res = client.get("/api/projects", headers=headers_a)
    assert projects_list_res.status_code == 200
    assert len(projects_list_res.json()) >= 1
    assert any(p["id"] == project_id for p in projects_list_res.json())

    # 5. Create Bot for User A
    bot_payload = {
        "project_id": project_id,
        "name": "Prycoons Property Assistant",
        "description": "Property discovery and customer assistance",
        "language": "English",
        "personality": "Friendly & professional",
        "welcome_message": "Hi! Welcome to Prycoons. How can I help you today?",
        "status": "Live"
    }
    bot_res = client.post("/api/bots", json=bot_payload, headers=headers_a)
    assert bot_res.status_code == 201
    bot_id = bot_res.json()["id"]
    assert bot_res.json()["name"] == "Prycoons Property Assistant"
    assert "shareable_slug" in bot_res.json()
    assert "prycoons-property-assistant" in bot_res.json()["shareable_slug"]

    # 6. Get Bot details
    bot_detail_res = client.get(f"/api/bots/{bot_id}", headers=headers_a)
    assert bot_detail_res.status_code == 200
    assert bot_detail_res.json()["name"] == "Prycoons Property Assistant"
    assert bot_detail_res.json()["project"]["industry"] == "Real Estate"

    # 7. Update Bot details and industry
    update_res = client.put(f"/api/bots/{bot_id}", json={
        "name": "Prycoons Real Estate AI Assistant",
        "industry": "Technology & SaaS",
        "welcome_message": "Hello! Looking for properties or tech solutions?"
    }, headers=headers_a)
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Prycoons Real Estate AI Assistant"
    assert update_res.json()["welcome_message"] == "Hello! Looking for properties or tech solutions?"

    # 8. Re-fetch Bot to ensure persistence of updated details
    refetched_bot = client.get(f"/api/bots/{bot_id}", headers=headers_a)
    assert refetched_bot.status_code == 200
    assert refetched_bot.json()["name"] == "Prycoons Real Estate AI Assistant"
    assert refetched_bot.json()["project"]["industry"] == "Technology & SaaS"

    # 9. Test Authorization Isolation: User B cannot view, edit, or delete User A's data
    signup_b = client.post("/api/auth/signup", json={
        "name": "User B",
        "email": "user_b_isolation@example.com",
        "password": "Password123!"
    })
    token_b = signup_b.json().get("access_token") or client.post("/api/auth/login", json={
        "email": "user_b_isolation@example.com",
        "password": "Password123!"
    }).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B fetching User A's project should return 404
    assert client.get(f"/api/projects/{project_id}", headers=headers_b).status_code == 404
    # User B updating User A's project should return 404
    assert client.put(f"/api/projects/{project_id}", json={"name": "Hacked"}, headers=headers_b).status_code == 404
    # User B fetching User A's bot should return 404
    assert client.get(f"/api/bots/{bot_id}", headers=headers_b).status_code == 404
    # User B updating User A's bot should return 404
    assert client.put(f"/api/bots/{bot_id}", json={"name": "Hacked"}, headers=headers_b).status_code == 404
    # User B deleting User A's bot should return 404
    assert client.delete(f"/api/bots/{bot_id}", headers=headers_b).status_code == 404
