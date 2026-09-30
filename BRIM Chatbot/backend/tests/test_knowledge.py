import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def auth_headers():
    signup_res = client.post("/api/auth/signup", json={
        "name": "Knowledge Test User",
        "email": "knowledge_user@example.com",
        "password": "Password123!"
    })
    token = signup_res.json().get("access_token") or client.post("/api/auth/login", json={
        "email": "knowledge_user@example.com",
        "password": "Password123!"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def other_user_headers():
    signup_res = client.post("/api/auth/signup", json={
        "name": "Other Test User",
        "email": "other_user@example.com",
        "password": "Password123!"
    })
    token = signup_res.json().get("access_token") or client.post("/api/auth/login", json={
        "email": "other_user@example.com",
        "password": "Password123!"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def user_bot(auth_headers):
    # Create project
    proj_res = client.post("/api/projects", json={
        "name": "Knowledge Project",
        "industry": "Real Estate"
    }, headers=auth_headers)
    proj_id = proj_res.json()["id"]

    # Create bot
    bot_res = client.post("/api/bots", json={
        "project_id": proj_id,
        "name": "Knowledge Bot",
        "welcome_message": "Hello!"
    }, headers=auth_headers)
    return bot_res.json()["id"]

def test_file_upload_txt(auth_headers, user_bot):
    file_content = b"Prycoons Realty has 3 BHK flats available in Gota starting at 80 Lakhs. Amenities include clubhouse, pool, and gym."
    files = {
        "file": ("properties.txt", io.BytesIO(file_content), "text/plain")
    }
    response = client.post(
        f"/api/bots/{user_bot}/knowledge/upload",
        files=files,
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "DOCUMENT"
    assert data["name"] == "properties.txt"
    assert data["processing_status"] == "COMPLETED"
    assert data["chunks_count"] >= 1
    assert data["file_size"] == len(file_content)

def test_invalid_file_type_rejected(auth_headers, user_bot):
    file_content = b"echo 'bad script'"
    files = {
        "file": ("script.exe", io.BytesIO(file_content), "application/octet-stream")
    }
    response = client.post(
        f"/api/bots/{user_bot}/knowledge/upload",
        files=files,
        headers=auth_headers
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_add_website_knowledge(auth_headers, user_bot):
    response = client.post(
        f"/api/bots/{user_bot}/knowledge/website",
        json={"url": "https://example.com", "name": "Example Domain"},
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "WEBSITE"
    assert data["source_url"] == "https://example.com"
    assert data["processing_status"] == "COMPLETED"
    assert data["chunks_count"] >= 1

def test_add_social_link_knowledge(auth_headers, user_bot):
    response = client.post(
        f"/api/bots/{user_bot}/knowledge/social",
        json={"url": "https://linkedin.com/company/prycoons"},
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "SOCIAL_LINK"
    assert data["processing_status"] == "COMPLETED"
    assert "LinkedIn" in data["name"]

def test_add_custom_instructions(auth_headers, user_bot):
    instr_payload = {
        "name": "Sales & Support Prompt Guidelines",
        "instructions": "Always be polite, address user budget first, and offer site visit bookings.",
        "tone": "Professional & courteous",
        "restrictions": "Do not quote discounts exceeding 5% without manager confirmation.",
        "objectives": "Capture customer name, email, and phone number for property visits."
    }
    response = client.post(
        f"/api/bots/{user_bot}/knowledge/instruction",
        json=instr_payload,
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "INSTRUCTION"
    assert data["processing_status"] == "COMPLETED"
    assert data["chunks_count"] >= 1

def test_list_and_delete_knowledge_source(auth_headers, user_bot):
    # 1. Create a source first
    create_res = client.post(
        f"/api/bots/{user_bot}/knowledge/instruction",
        json={"name": "Temporary Guideline", "instructions": "This is a temporary instruction to delete."},
        headers=auth_headers
    )
    assert create_res.status_code == 201
    source_to_delete = create_res.json()["id"]

    # 2. List sources
    list_res = client.get(f"/api/bots/{user_bot}/knowledge", headers=auth_headers)
    assert list_res.status_code == 200
    sources = list_res.json()
    assert len(sources) >= 1
    assert any(s["id"] == source_to_delete for s in sources)

    # 3. Delete source
    del_res = client.delete(f"/api/knowledge/{source_to_delete}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["id"] == source_to_delete

    # 4. Verify deleted
    get_res = client.get(f"/api/knowledge/{source_to_delete}", headers=auth_headers)
    assert get_res.status_code == 404

def test_knowledge_ownership_isolation(auth_headers, other_user_headers, user_bot):
    # Create instruction under User A's bot
    response = client.post(
        f"/api/bots/{user_bot}/knowledge/instruction",
        json={"name": "Confidential Instructions", "instructions": "Internal policies only."},
        headers=auth_headers
    )
    source_id = response.json()["id"]

    # User B should receive 404 when listing User A's bot knowledge
    assert client.get(f"/api/bots/{user_bot}/knowledge", headers=other_user_headers).status_code == 404

    # User B should receive 404 when uploading to User A's bot
    files = {"file": ("test.txt", io.BytesIO(b"data"), "text/plain")}
    assert client.post(f"/api/bots/{user_bot}/knowledge/upload", files=files, headers=other_user_headers).status_code == 404

    # User B should receive 404 when viewing or deleting User A's knowledge source
    assert client.get(f"/api/knowledge/{source_id}", headers=other_user_headers).status_code == 404
    assert client.delete(f"/api/knowledge/{source_id}", headers=other_user_headers).status_code == 404
