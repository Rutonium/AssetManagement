import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient


os.environ.setdefault("ASSET_MANAGEMENT_DB_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("TIMEAPP_DB_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("LOCAL_ADMIN_PASSWORD", "admin-test-pin")
os.environ.setdefault("SESSION_SIGNING_SECRET", "x" * 48)

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import AssetMan as app_module


class FakeDb:
    def __init__(self):
        self.instance = None
        self.commits = 0
        self.rollbacks = 0
        self.added = []

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def execute(self, *args, **kwargs):
        class _Result:
            def all(self_inner):
                return []

            def first(self_inner):
                return None

            def scalars(self_inner):
                return self_inner

        return _Result()

    def get(self, model, identifier):
        model_name = getattr(model, "__name__", "")
        if model_name == "ToolInstance" and self.instance and int(identifier) == int(self.instance.ToolInstanceID):
            return self.instance
        return None


class SecurityAndFlowTests(unittest.TestCase):
    def setUp(self):
        self.fake_db = FakeDb()
        app_module.app.dependency_overrides[app_module.get_asset_db] = lambda: self.fake_db
        self.client = TestClient(app_module.app)

    def tearDown(self):
        app_module.app.dependency_overrides.clear()

    def test_login_logout_revokes_session_token(self):
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-test-pin"},
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["sessionToken"]
        headers = {"X-Session-Token": token}

        me_before = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_before.status_code, 200)

        logout = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout.status_code, 200)

        me_after = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_after.status_code, 401)

    def test_login_persists_with_cookie_session(self):
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-test-pin"},
        )
        self.assertEqual(login.status_code, 200)

        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual((me.json().get("user") or {}).get("role"), "Admin")
        set_cookie = login.headers.get("set-cookie", "")
        self.assertIn("asset_management_session=", set_cookie)

    def test_kiosk_lend_requires_valid_pin(self):
        original_directory = app_module.get_employee_directory
        original_verify = app_module.verify_password
        app_module.get_employee_directory = lambda force_refresh=False: {
            "123": {
                "number": "123",
                "normalizedNumber": "123",
                "name": "Test User",
                "initials": "TU",
                "displayName": "TU - Test User",
                "email": "",
                "departmentCode": "",
            }
        }
        app_module.verify_password = lambda db, employee_id, pin_code: False
        try:
            response = self.client.post(
                "/api/kiosk/lend",
                json={
                    "employeeID": 123,
                    "pinCode": "9999",
                    "purpose": "Test",
                    "startDate": "2026-02-21",
                    "endDate": "2026-02-22",
                    "rentalItems": [{"toolID": 1, "quantity": 1}],
                },
            )
            self.assertEqual(response.status_code, 401)
        finally:
            app_module.get_employee_directory = original_directory
            app_module.verify_password = original_verify

    def test_employee_login_requires_provisioned_atlas_user(self):
        original_directory = app_module.get_employee_directory
        app_module.get_employee_directory = lambda force_refresh=False: {
            "123": {
                "number": "123",
                "normalizedNumber": "123",
                "name": "Test User",
                "initials": "TU",
                "displayName": "TU - Test User",
                "email": "",
                "departmentCode": "",
            }
        }
        try:
            response = self.client.post(
                "/api/auth/login",
                json={"employeeID": 123, "pinCode": "1234"},
            )
            self.assertEqual(response.status_code, 401)
        finally:
            app_module.get_employee_directory = original_directory

    def test_warehouse_assign_updates_instance(self):
        self.fake_db.instance = SimpleNamespace(
            ToolInstanceID=77,
            LocationCode=None,
            WarehouseID=None,
            UpdatedDate=None,
        )
        response = self.client.post(
            "/api/warehouse/assign",
            json={"toolID": 77, "warehouseID": 2, "locationCode": "B-4"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake_db.instance.WarehouseID, 2)
        self.assertEqual(self.fake_db.instance.LocationCode, "B-4")

    def test_auth_users_returns_provisioned_atlas_users_only(self):
        original_list_provisioned_users = app_module.list_provisioned_users
        app_module.list_provisioned_users = lambda db: [
            {"employeeID": 101, "displayName": "Employee #101", "role": "User", "rights": {"checkout": True}},
            {"employeeID": 202, "displayName": "Employee #202", "role": "Admin", "rights": {"manageUsers": True}},
        ]
        try:
            response = self.client.get("/api/auth/users")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body, [{"employeeID": 101, "displayName": "Employee #101"}, {"employeeID": 202, "displayName": "Employee #202"}])
        finally:
            app_module.list_provisioned_users = original_list_provisioned_users

    def test_provisioned_user_can_login_without_employee_directory_entry(self):
        original_get_user_record = app_module.get_user_record
        original_verify_password = app_module.verify_password
        original_get_employee_directory = app_module.get_employee_directory

        app_module.get_user_record = lambda db, employee_id: {
            "employeeID": int(employee_id),
            "role": "Admin",
            "rights": {"manageUsers": True},
            "isProvisioned": True,
        }
        app_module.verify_password = lambda db, employee_id, pin_code: True
        app_module.get_employee_directory = lambda force_refresh=False: {}
        try:
            response = self.client.post(
                "/api/auth/login",
                json={"employeeID": 999999, "pinCode": "1234"},
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual((body.get("user") or {}).get("employeeID"), 999999)
            self.assertEqual((body.get("user") or {}).get("displayName"), "Employee #999999")
        finally:
            app_module.get_user_record = original_get_user_record
            app_module.verify_password = original_verify_password
            app_module.get_employee_directory = original_get_employee_directory


if __name__ == "__main__":
    unittest.main()
