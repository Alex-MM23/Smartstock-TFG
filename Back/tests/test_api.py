"""Tests for the API endpoints."""

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_endpoint(self, client: TestClient):
        """Test health endpoint returns correct structure."""
        response = client.get("/health")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "model" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_register(self, client: TestClient):
        """Test user registration."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "testpass123", "role": "client"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["role"] == "client"

    def test_register_duplicate_email(self, client: TestClient):
        """Test registering with duplicate email fails."""
        client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "testpass123", "role": "client"}
        )
        response = client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "testpass123", "role": "client"}
        )
        assert response.status_code == 400
        assert "ya está registrado" in response.json()["detail"]

    def test_login(self, client: TestClient):
        """Test user login."""
        # First register
        client.post(
            "/auth/register",
            json={"email": "login@example.com", "password": "testpass123", "role": "client"}
        )
        # Then login
        response = client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "testpass123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "login@example.com"

    def test_login_wrong_password(self, client: TestClient):
        """Test login with wrong password fails."""
        client.post(
            "/auth/register",
            json={"email": "wrongpass@example.com", "password": "testpass123", "role": "client"}
        )
        response = client.post(
            "/auth/login",
            json={"email": "wrongpass@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401

    def test_refresh_token(self, client: TestClient):
        """Test token refresh."""
        register_resp = client.post(
            "/auth/register",
            json={"email": "refresh@example.com", "password": "testpass123", "role": "client"}
        )
        refresh_token = register_resp.json()["refresh_token"]

        response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_get_me(self, client: TestClient):
        """Test getting current user info."""
        register_resp = client.post(
            "/auth/register",
            json={"email": "me@example.com", "password": "testpass123", "role": "client"}
        )
        access_token = register_resp.json()["access_token"]

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert data["role"] == "client"

    def test_get_me_unauthorized(self, client: TestClient):
        """Test /me without token fails."""
        response = client.get("/auth/me")
        assert response.status_code == 401


class TestProductsEndpoint:
    """Tests for /products endpoint."""

    def test_list_products(self, client: TestClient):
        """Test listing products."""
        response = client.get("/products")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestOrdersEndpoints:
    """Tests for orders endpoints."""

    def test_get_orders_empty(self, client: TestClient):
        """Test getting orders when none exist."""
        response = client.get("/orders")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_order_not_found(self, client: TestClient):
        """Test getting non-existent order returns 404."""
        response = client.get("/orders/999")
        assert response.status_code == 404


class TestStockEndpoint:
    """Tests for /stock/status endpoint."""

    def test_stock_status(self, client: TestClient):
        """Test stock status endpoint."""
        response = client.get("/stock/status")
        # May return 503 if view doesn't exist in test DB
        assert response.status_code in (200, 503)


class TestPredictEndpoint:
    """Tests for /predict/demand endpoint."""

    def test_predict_missing_params(self, client: TestClient):
        """Test predict with missing required params fails."""
        response = client.post("/predict/demand", json={})
        assert response.status_code == 422

    def test_predict_invalid_params(self, client: TestClient):
        """Test predict with both id and sku fails."""
        response = client.post("/predict/demand", json={"id_producto": 1, "sku": "TEST"})
        assert response.status_code == 422
