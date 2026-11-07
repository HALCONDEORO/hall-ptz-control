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
