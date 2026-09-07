from app.local_compute.protocol import ProtocolCommand, parse_protocol_uri


def test_protocol_allows_only_fixed_no_payload_commands():
    assert parse_protocol_uri("zkd://start") is ProtocolCommand.START
    assert parse_protocol_uri("zkd://start/") is ProtocolCommand.START
    assert parse_protocol_uri("zkd://open") is ProtocolCommand.OPEN
    assert parse_protocol_uri("zkd://open/") is ProtocolCommand.OPEN


def test_protocol_rejects_untrusted_command_payloads():
    for value in (
        "zkd://run?command=calc.exe",
        "zkd://exec?path=C:/secret",
        "zkd://open-file?path=C:/secret.pdf",
        "zkd://start/anything",
        "https://rag.zkd.id.vn",
        "zkd://unknown",
    ):
        assert parse_protocol_uri(value) is None
