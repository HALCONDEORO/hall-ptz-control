def test_acceptance_checks_the_protected_administrator_store():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "scripts/validate_rpi_acceptance.sh").read_text()
    assert "for _secret in /var/lib/khptz/password.enc /etc/khptz/secrets/admin.enc; do" in source
