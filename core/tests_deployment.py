"""
Deployment validation tests.
Run with: pytest core/tests_deployment.py -v
"""
import pytest
from django.core.management import call_command
from django.test import override_settings


@pytest.mark.django_db
class TestValidateDeployment:
    """Test validate_deployment command."""

    @override_settings(
        SECRET_KEY="test-production-secret-not-dev-default",
        ALLOWED_HOSTS=["testserver", "localhost"],
    )
    def test_validate_deployment_runs_with_skips(self):
        """Command runs without crash when skipping DB/migrations/static."""
        call_command("validate_deployment", "--skip-db", "--skip-migrations", "--skip-static")

    @override_settings(
        SECRET_KEY="dev-secret-key-change-in-production",
        ALLOWED_HOSTS=["localhost"],
    )
    def test_validate_deployment_fails_on_dev_secret(self):
        """Fails when SECRET_KEY is dev default."""
        with pytest.raises(SystemExit) as exc:
            call_command("validate_deployment", "--skip-db", "--skip-migrations", "--skip-static")
        assert exc.value.code == 1
