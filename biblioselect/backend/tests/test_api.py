from conftest import VALID_REQUEST, as_user
from app.workflow import Role

REQUESTER = "docente@example.edu"
LIBRARIAN = "bibliotecario@example.edu"
PROGRAM_DIRECTOR = "director.programa@example.edu"
BUDGET = "presupuesto@example.edu"
ACQUISITIONS = "adquisiciones@example.edu"
ADMIN = "admin@example.edu"
AUDITOR = "auditor@example.edu"


def create(client, payload=None):
    return create_as(client, REQUESTER, payload)


def create_as(client, email, payload=None):
    res = client.post("/api/requests", json=payload or VALID_REQUEST, headers=as_user(email))
    assert res.status_code == 201, res.text
    return res.json()


def act(client, req_id, action, email, reason=None):
    return client.post(
        f"/api/requests/{req_id}/transitions",
        json={"action": action, "reason": reason},
        headers=as_user(email),
    )


def test_requires_authentication(app_client):
    assert app_client.get("/api/requests").status_code == 401
    assert app_client.get("/api/requests", headers=as_user("nadie@example.edu")).status_code == 401


def test_create_request_returns_reference_and_submitted_status(app_client):
    data = create(app_client)
    assert data["reference"].startswith("BS-")
    assert data["status"] == "submitted"
    assert data["isbn"] == "9780306406157"  # normalizado
    assert "start_review" not in data["available_actions"]  # solo bibliotecario
    assert data["quantity"] == 2


def test_invalid_isbn_is_rejected(app_client):
    res = app_client.post(
        "/api/requests", json={**VALID_REQUEST, "isbn": "9780306406158"}, headers=as_user(REQUESTER)
    )
    assert res.status_code == 422


def test_full_happy_path_through_all_approvals(app_client):
    req = create(app_client)
    rid = req["id"]
    assert act(app_client, rid, "start_review", LIBRARIAN).json()["status"] == "under_review"
    assert act(app_client, rid, "send_to_approval", LIBRARIAN).json()["status"] == "awaiting_approval"
    assert act(app_client, rid, "approve_program", PROGRAM_DIRECTOR).json()["status"] == "program_approved"
    assert act(app_client, rid, "approve_budget", BUDGET).json()["status"] == "budget_approved"
    assert act(app_client, rid, "complete_acquisition", ACQUISITIONS).json()["status"] == "completed"

    hist = app_client.get(f"/api/requests/{rid}/history", headers=as_user(REQUESTER)).json()
    assert [h["action"] for h in hist] == [
        "create", "start_review", "send_to_approval", "approve_program", "approve_budget", "complete_acquisition",
    ]


def test_librarian_approval_does_not_authorize_budget(app_client):
    rid = create(app_client)["id"]
    act(app_client, rid, "start_review", LIBRARIAN)
    act(app_client, rid, "send_to_approval", LIBRARIAN)
    res = act(app_client, rid, "approve_budget", BUDGET)
    assert res.status_code == 409  # el estado aún no pasó por programa


def test_librarian_cannot_approve_program_decision(app_client):
    rid = create(app_client)["id"]
    act(app_client, rid, "start_review", LIBRARIAN)
    act(app_client, rid, "send_to_approval", LIBRARIAN)
    assert act(app_client, rid, "approve_program", LIBRARIAN).status_code == 403


def test_director_cannot_approve_own_request(app_client, make_user):
    # El director también crea solicitudes: aun siendo director de la facultad, no aprueba la propia.
    make_user("doble@example.edu", [Role.PROGRAM_DIRECTOR], faculty="Facultad de Ingeniería")
    rid = create_as(app_client, "doble@example.edu")["id"]
    act(app_client, rid, "start_review", LIBRARIAN)
    act(app_client, rid, "send_to_approval", LIBRARIAN)
    assert act(app_client, rid, "approve_program", "doble@example.edu").status_code == 403
    assert act(app_client, rid, "approve_program", PROGRAM_DIRECTOR).status_code == 200


def test_program_director_only_sees_and_approves_own_faculty(app_client, make_user):
    make_user("otro.director@example.edu", [Role.PROGRAM_DIRECTOR], faculty="Facultad de Derecho")
    rid = create(app_client)["id"]
    act(app_client, rid, "start_review", LIBRARIAN)
    act(app_client, rid, "send_to_approval", LIBRARIAN)
    assert app_client.get(f"/api/requests/{rid}", headers=as_user("otro.director@example.edu")).status_code == 404
    assert act(app_client, rid, "approve_program", "otro.director@example.edu").status_code == 404


def test_rejection_requires_reason(app_client):
    rid = create(app_client)["id"]
    act(app_client, rid, "start_review", LIBRARIAN)
    assert act(app_client, rid, "reject_library", LIBRARIAN).status_code == 422
    assert act(app_client, rid, "reject_library", LIBRARIAN, reason="Ya existe en el catálogo").status_code == 200


def test_requester_can_edit_only_in_editable_states(app_client):
    rid = create(app_client)["id"]
    res = app_client.patch(f"/api/requests/{rid}", json={"quantity": 5}, headers=as_user(REQUESTER))
    assert res.status_code == 200 and res.json()["quantity"] == 5

    act(app_client, rid, "start_review", LIBRARIAN)
    res = app_client.patch(f"/api/requests/{rid}", json={"quantity": 6}, headers=as_user(REQUESTER))
    assert res.status_code == 409


def test_patch_validates_merged_payload(app_client):
    rid = create(app_client)["id"]
    res = app_client.patch(f"/api/requests/{rid}", json={"isbn": "1234567890"}, headers=as_user(REQUESTER))
    assert res.status_code == 422


def test_patch_cannot_change_requester_email(app_client):
    rid = create(app_client)["id"]
    res = app_client.patch(
        f"/api/requests/{rid}", json={"requester_email": "otro@example.edu"}, headers=as_user(REQUESTER)
    )
    assert res.status_code == 422  # sin campos modificables tras filtrar


def test_other_requesters_cannot_see_request(app_client, make_user):
    make_user("otro@example.edu", [])
    rid = create(app_client)["id"]
    assert app_client.get(f"/api/requests/{rid}", headers=as_user("otro@example.edu")).status_code == 404


def test_requester_cancels_own_request_with_reason(app_client):
    rid = create(app_client)["id"]
    res = app_client.post(f"/api/requests/{rid}/cancel", json={"reason": "Ya no es necesario"}, headers=as_user(REQUESTER))
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"
    assert app_client.post(f"/api/requests/{rid}/cancel", json={"reason": "otra vez"}, headers=as_user(LIBRARIAN)).status_code == 409


def test_requester_cannot_cancel_after_review_starts(app_client):
    rid = create(app_client)["id"]
    act(app_client, rid, "start_review", LIBRARIAN)
    res = app_client.post(f"/api/requests/{rid}/cancel", json={"reason": "Cambié de opinión"}, headers=as_user(REQUESTER))
    assert res.status_code == 403


def test_listing_is_scoped_by_role(app_client):
    create(app_client)
    assert len(app_client.get("/api/requests", headers=as_user(REQUESTER)).json()) == 1
    assert len(app_client.get("/api/requests", headers=as_user(LIBRARIAN)).json()) == 1
    assert app_client.get("/api/requests", headers=as_user(BUDGET)).json()[0]["reference"].startswith("BS-")


def test_admin_creates_user_and_auditor_reads_audit(app_client):
    res = app_client.post(
        "/api/admin/users",
        json={"email": "nuevo@example.edu", "full_name": "Nuevo Usuario", "roles": ["librarian"]},
        headers=as_user(ADMIN),
    )
    assert res.status_code == 201
    assert app_client.post(
        "/api/admin/users",
        json={"email": "x@example.edu", "full_name": "No Admin"},
        headers=as_user(LIBRARIAN),
    ).status_code == 403

    create(app_client)
    entries = app_client.get("/api/audit", headers=as_user(AUDITOR)).json()
    assert any(e["action"] == "request.create" for e in entries)
    assert all("password" not in e["description"].lower() for e in entries)
    assert app_client.get("/api/audit", headers=as_user(REQUESTER)).status_code == 403


def test_every_transition_writes_audit(app_client):
    rid = create(app_client)["id"]
    act(app_client, rid, "start_review", LIBRARIAN)
    entries = app_client.get(f"/api/audit?request_id={rid}", headers=as_user(AUDITOR)).json()
    actions = {e["action"] for e in entries}
    assert {"request.create", "request.start_review"} <= actions
