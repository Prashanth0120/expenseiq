# =========================================================
# TEST ROOT ENDPOINT
# =========================================================

def test_root(client):

    response = client.get("/")

    assert response.status_code == 200

    assert response.json() == {
        "message": "ExpenseIQ is alive"
    }


# =========================================================
# TEST SIGNUP
# =========================================================

def test_signup(client):

    response = client.post(
        "/signup",
        json={
            "username": "pytestuser",
            "email": "pytestuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["username"] == "pytestuser"
    assert data["email"] == "pytestuser@example.com"



def test_login(client):
    # Create user first
    client.post(
        "/signup",
        json={
            "username": "loginuser",
            "email": "loginuser@example.com",
            "password": "TestPassword123"
        }
    )

    # Login uses form data, NOT JSON
    response = client.post(
        "/login",
        data={
            "username": "loginuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data

    assert data["token_type"] == "bearer"


def test_get_me(client):
    # 1. Create user
    client.post(
        "/signup",
        json={
            "username": "meuser",
            "email": "meuser@example.com",
            "password": "TestPassword123"
        }
    )

    # 2. Login
    login_response = client.post(
        "/login",
        data={
            "username": "meuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert login_response.status_code == 200

    # 3. Get JWT token
    token = login_response.json()["access_token"]

    # 4. Send JWT in Authorization header
    response = client.get(
        "/me",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    # 5. Verify response
    assert response.status_code == 200

    data = response.json()

    assert data["username"] == "meuser"
    assert data["email"] == "meuser@example.com"


def test_create_expense(client):
    # Create user
    client.post(
        "/signup",
        json={
            "username": "expenseuser",
            "email": "expenseuser@example.com",
            "password": "TestPassword123"
        }
    )

    # Login
    login_response = client.post(
        "/login",
        data={
            "username": "expenseuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    # Create expense
    response = client.post(
        "/expenses",
        json={
            "description": "Petrol",
            "amount": 1800,
            "category": "Travel"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["description"] == "Petrol"
    assert data["amount"] == 1800
    assert data["category"] == "Travel"

    # Database should generate these
    assert "id" in data
    assert "created_at" in data


def test_get_expenses(client):
    # Create user
    client.post(
        "/signup",
        json={
            "username": "listuser",
            "email": "listuser@example.com",
            "password": "TestPassword123"
        }
    )

    # Login
    login_response = client.post(
        "/login",
        data={
            "username": "listuser@example.com",
            "password": "TestPassword123"
        }
    )

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Create 3 expenses
    expenses = [
        {
            "description": "Petrol",
            "amount": 1800,
            "category": "Travel"
        },
        {
            "description": "Lunch",
            "amount": 500,
            "category": "Food"
        },
        {
            "description": "Movie",
            "amount": 300,
            "category": "Entertainment"
        }
    ]

    for expense in expenses:
        response = client.post(
            "/expenses",
            json=expense,
            headers=headers
        )

        assert response.status_code == 200

    # Get only 2 expenses
    response = client.get(
        "/expenses?skip=0&limit=2",
        headers=headers
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert data["count"] == 2
    assert len(data["data"]) == 2


def test_expense_filters_search_sort(client):
    # Create user
    client.post(
        "/signup",
        json={
            "username": "filteruser",
            "email": "filteruser@example.com",
            "password": "TestPassword123"
        }
    )

    # Login
    login_response = client.post(
        "/login",
        data={
            "username": "filteruser@example.com",
            "password": "TestPassword123"
        }
    )

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Create expenses
    test_expenses = [
        {
            "description": "Petrol",
            "amount": 1800,
            "category": "Travel"
        },
        {
            "description": "Flight Ticket",
            "amount": 5000,
            "category": "Travel"
        },
        {
            "description": "Lunch",
            "amount": 500,
            "category": "Food"
        }
    ]

    for expense in test_expenses:
        response = client.post(
            "/expenses",
            json=expense,
            headers=headers
        )

        assert response.status_code == 200

    # -------------------------
    # Test category filter
    # -------------------------

    response = client.get(
        "/expenses?category=Travel",
        headers=headers
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2

    for expense in data["data"]:
        assert expense["category"] == "Travel"

    # -------------------------
    # Test search
    # -------------------------

    response = client.get(
        "/expenses?search=Petrol",
        headers=headers
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["data"][0]["description"] == "Petrol"

    # -------------------------
    # Test amount range
    # -------------------------

    response = client.get(
        "/expenses?min_amount=1000&max_amount=2000",
        headers=headers
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["data"][0]["amount"] == 1800

    # -------------------------
    # Test highest sorting
    # -------------------------

    response = client.get(
        "/expenses?sort=highest",
        headers=headers
    )

    assert response.status_code == 200

    data = response.json()

    assert data["data"][0]["amount"] == 5000


def test_update_patch_delete_expense(client):
    # Create user
    client.post(
        "/signup",
        json={
            "username": "cruduser",
            "email": "cruduser@example.com",
            "password": "TestPassword123"
        }
    )

    # Login
    login_response = client.post(
        "/login",
        data={
            "username": "cruduser@example.com",
            "password": "TestPassword123"
        }
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # --------------------------------
    # CREATE
    # --------------------------------

    create_response = client.post(
        "/expenses",
        json={
            "description": "Petrol",
            "amount": 1800,
            "category": "Travel"
        },
        headers=headers
    )

    assert create_response.status_code == 200

    expense_id = create_response.json()["id"]

    # --------------------------------
    # PUT - FULL UPDATE
    # --------------------------------

    put_response = client.put(
        f"/expenses/{expense_id}",
        json={
            "description": "Diesel",
            "amount": 2000,
            "category": "Travel"
        },
        headers=headers
    )

    assert put_response.status_code == 200

    put_data = put_response.json()

    assert put_data["description"] == "Diesel"
    assert put_data["amount"] == 2000
    assert put_data["category"] == "Travel"

    # --------------------------------
    # PATCH - PARTIAL UPDATE
    # --------------------------------

    patch_response = client.patch(
        f"/expenses/{expense_id}",
        json={
            "amount": 2200
        },
        headers=headers
    )

    assert patch_response.status_code == 200

    patch_data = patch_response.json()

    assert patch_data["description"] == "Diesel"
    assert patch_data["amount"] == 2200
    assert patch_data["category"] == "Travel"

    # --------------------------------
    # DELETE
    # --------------------------------

    delete_response = client.delete(
        f"/expenses/{expense_id}",
        headers=headers
    )

    assert delete_response.status_code == 200

    assert delete_response.json() == {
        "message": "Expense deleted successfully"
    }

    # --------------------------------
    # VERIFY DELETION
    # --------------------------------

    get_response = client.get(
        f"/expenses/{expense_id}",
        headers=headers
    )

    assert get_response.status_code == 404
    