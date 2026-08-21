import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from services import change_admin_password


class ChangeAdminPasswordServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_username_returns_generic_credentials_error(self):
        with patch("services.get_admin_by_username", return_value=None):
            result = await change_admin_password(
                "unknown",
                "old-password",
                "new-password",
            )

        self.assertEqual(result, (False, "Incorrect credentials", 401))

    async def test_wrong_current_password_returns_generic_credentials_error(self):
        admin = {"password": "stored-hash"}
        with (
            patch("services.get_admin_by_username", return_value=admin),
            patch("services.verify_password", return_value=False),
        ):
            result = await change_admin_password("admin", "wrong-password", "new-password")

        self.assertEqual(result, (False, "Incorrect credentials", 401))

    async def test_new_password_must_differ_from_current_password(self):
        admin = {"password": "stored-hash"}
        with (
            patch("services.get_admin_by_username", return_value=admin),
            patch("services.verify_password", side_effect=[True, True]),
        ):
            result = await change_admin_password("admin", "same-password", "same-password")

        self.assertEqual(
            result,
            (False, "New password must differ from the current one.", 400),
        )

    async def test_new_password_must_be_at_least_eight_characters(self):
        admin = {"password": "stored-hash"}
        with (
            patch("services.get_admin_by_username", return_value=admin),
            patch("services.verify_password", side_effect=[True, False]),
        ):
            result = await change_admin_password("admin", "old-password", "short")

        self.assertEqual(
            result,
            (False, "Password must be at least 8 characters.", 400),
        )

    async def test_success_hashes_and_persists_the_new_password(self):
        admin = {"password": "stored-hash"}
        with (
            patch("services.get_admin_by_username", return_value=admin),
            patch("services.verify_password", side_effect=[True, False]),
            patch("services.hash_password", return_value="new-hash") as hash_password,
            patch("services.update_admin_password", return_value=True) as update_password,
        ):
            result = await change_admin_password(
                "admin",
                "old-password",
                "new-password",
            )

        self.assertEqual(result, (True, "Password updated successfully.", 200))
        hash_password.assert_called_once_with("new-password")
        update_password.assert_called_once_with("admin", "stored-hash", "new-hash")

    async def test_database_read_error_returns_safe_server_error(self):
        with (
            patch(
                "services.get_admin_by_username",
                side_effect=RuntimeError("db unavailable"),
            ),
            patch("services.logger.exception") as log_exception,
        ):
            result = await change_admin_password("admin", "old-password", "new-password")

        self.assertEqual(result, (False, "Unable to update password.", 500))
        log_exception.assert_called_once_with(
            "Failed to load admin credentials for password change"
        )

    async def test_database_write_error_returns_safe_server_error(self):
        admin = {"password": "stored-hash"}
        with (
            patch("services.get_admin_by_username", return_value=admin),
            patch("services.verify_password", side_effect=[True, False]),
            patch("services.hash_password", return_value="new-hash"),
            patch(
                "services.update_admin_password",
                side_effect=RuntimeError("db unavailable"),
            ),
            patch("services.logger.exception") as log_exception,
        ):
            result = await change_admin_password("admin", "old-password", "new-password")

        self.assertEqual(result, (False, "Unable to update password.", 500))
        log_exception.assert_called_once_with(
            "Failed to persist admin password change"
        )


class ChangeAdminPasswordEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_endpoint_returns_service_status_and_exact_response_shape(self):
        payload = {
            "username": "admin",
            "currentPassword": "old-password",
            "newPassword": "new-password",
        }
        cases = [
            ((True, "Password updated successfully.", 200), 200),
            ((False, "Incorrect credentials", 401), 401),
            ((False, "Password must be at least 8 characters.", 400), 400),
        ]

        for service_result, expected_status_code in cases:
            with self.subTest(status_code=expected_status_code):
                change_password = AsyncMock(return_value=service_result)
                with patch("main.change_admin_password", new=change_password):
                    response = self.client.post(
                        "/dashboard/v1/admin-change-password",
                        json=payload,
                    )

                self.assertEqual(response.status_code, expected_status_code)
                self.assertEqual(
                    response.json(),
                    {"status": service_result[0], "message": service_result[1]},
                )
                change_password.assert_awaited_once_with(
                    "admin",
                    "old-password",
                    "new-password",
                )

    def test_all_request_fields_are_required(self):
        with patch("main.change_admin_password", new=AsyncMock()) as change_password:
            response = self.client.post(
                "/dashboard/v1/admin-change-password",
                json={
                    "username": "admin",
                    "currentPassword": "old-password",
                },
            )

        self.assertEqual(response.status_code, 422)
        change_password.assert_not_awaited()

    def test_openapi_contract_uses_camel_case_request_fields(self):
        document = app.openapi()
        operation = document["paths"]["/dashboard/v1/admin-change-password"]["post"]
        request_schema = operation["requestBody"]["content"]["application/json"][
            "schema"
        ]
        schema_name = request_schema["$ref"].rsplit("/", 1)[-1]
        properties = document["components"]["schemas"][schema_name]["properties"]

        self.assertEqual(
            set(properties),
            {"username", "currentPassword", "newPassword"},
        )
        self.assertTrue({"200", "400", "401"}.issubset(operation["responses"]))


if __name__ == "__main__":
    unittest.main()
