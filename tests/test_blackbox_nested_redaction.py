"""Support output must redact secret fields and text inside event sequences."""
import json
import zipfile

from application.support_bundle_service import SupportBundleService
from domain.blackbox_event import redact_event_dict


def test_redaction_walks_arbitrarily_nested_sequences_without_mutating_input():
    source = {"events": [[{"password": "synthetic-list-password"}],
                         ({"token": "synthetic-tuple-token"},)],
              "summary": "retry password=synthetic-text-password host=test",
              "count": 3, "ok": True}
    result = redact_event_dict(source)
    encoded = json.dumps(result)
    assert "synthetic-" not in encoded
    assert result["count"] == 3
    assert result["ok"] is True
    assert "host=test" in result["summary"]
    assert source["events"][0][0]["password"] == "synthetic-list-password"


def test_exported_incident_and_events_do_not_leak_sequence_or_text_secrets(tmp_path):
    payload = {"event_type": "SyntheticDiagnostic", "last_events": [
        {"extra": {"password": "synthetic-export-password"}},
        ["token=synthetic-export-token"],
    ], "summary": "password=synthetic-export-summary"}
    incidents = tmp_path / "incidents"
    incidents.mkdir()
    incident = incidents / "incident-synthetic.json"
    original = json.dumps(payload)
    incident.write_text(original, encoding="utf-8")

    class Recorder:
        def export_for_support(self, maximum):
            return [payload]

    service = SupportBundleService(output_dir=tmp_path / "out",
                                   incidents_dir=incidents, flight_recorder=Recorder())
    bundle = service.create()
    assert bundle is not None
    with zipfile.ZipFile(bundle) as archive:
        for name in ("blackbox/recent_events.jsonl",
                     "blackbox/incidents/incident-synthetic.json"):
            output = archive.read(name).decode("utf-8")
            assert "synthetic-export-" not in output
            assert "SyntheticDiagnostic" in output
            assert "REDACTED" in output
    assert incident.read_text(encoding="utf-8") == original


def test_zip_redacts_all_shared_secret_keys_and_quoted_values(tmp_path):
    keys = ["passwd", "pwd", "authorization", "auth", "signing_key",
            "license_key", "licence_key", "access_key", "apikey", "privatekey",
            "client_secret", "bearer", "ssh_password", "license_private_key"]
    payload = {"last_events": [[{key: "SYNTHETIC_KEY_" + key for key in keys}]],
               "summary": 'password="safe words SYNTHETIC_QUOTED_TAIL" host=test',
               "extra": ["token='safe words SYNTHETIC_SINGLE_TAIL' next=ok",
                         'password="escaped \\" words SYNTHETIC_ESCAPED_TAIL" end=ok',
                         'password="unterminated SYNTHETIC_UNCLOSED_TAIL']}

    class Recorder:
        def export_for_support(self, maximum):
            return [payload]

    incidents = tmp_path / "incidents"
    incidents.mkdir()
    (incidents / "incident-quoted.json").write_text(json.dumps(payload), encoding="utf-8")
    bundle = SupportBundleService(output_dir=tmp_path / "out", incidents_dir=incidents,
                                  flight_recorder=Recorder()).create()
    assert bundle is not None
    with zipfile.ZipFile(bundle) as archive:
        for name in ("blackbox/recent_events.jsonl", "blackbox/incidents/incident-quoted.json"):
            output = archive.read(name).decode("utf-8")
            assert "SYNTHETIC_" not in output
            assert "host=test" in output
            assert "next=ok" in output
            assert "end=ok" in output
