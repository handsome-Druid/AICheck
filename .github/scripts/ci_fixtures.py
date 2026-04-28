from __future__ import annotations

import argparse
import csv
import json
import random
import time
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import ClassVar, TypedDict, cast
from urllib.parse import urlsplit


FIELDNAMES: list[str] = [
    "port",
    "modelID",
    "模型名",
    "监控id",
    "GPU型号",
    "GPU数量",
    "上下文长度（K）",
    "容器名",
    "调用方法",
]

CASE_KINDS: list[str] = [
    "exact_single",
    "exact_many",
    "empty",
    "extra_single",
    "extra_many",
    "both_single",
    "both_many",
    "invalid_json",
    "http_500",
    "timeout",
]

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18080
JSON_CONTENT_TYPE = "application/json; charset=utf-8"
TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"


class CasePayload(TypedDict, total=False):
    case_kind: str
    status_code: int
    kind: str
    models: list[str]
    delay_seconds: float
    message: str


ManifestMap = dict[str, CasePayload]


class XlsxSettings(TypedDict):
    input_path: str
    input_sheet_name: str


class CsvSettings(TypedDict):
    input_path: str
    output_path: str


class SourceSettings(TypedDict):
    last_type: str


class EndFlagSettings(TypedDict):
    tag: str
    value: str


class SettingsPayload(TypedDict):
    xlsx: XlsxSettings
    csv: CsvSettings
    source: SourceSettings
    end_flag: EndFlagSettings
    pass_port: list[int]


def _unique_models(rng: random.Random, prefix: str, count: int, excluded: Sequence[str]) -> list[str]:
    models: list[str] = []
    excluded_set = set(excluded)

    while len(models) < count:
        candidate = f"{prefix}-{rng.randrange(1_000_000):06d}"
        if candidate in excluded_set or candidate in models:
            continue
        models.append(candidate)

    return models


def _build_models_with_expected(rng: random.Random, expected_model: str, extra_count: int) -> list[str]:
    models = [expected_model, *_unique_models(rng, "extra", extra_count, [expected_model])]
    rng.shuffle(models)
    return models


def _case_sequence(row_count: int, rng: random.Random) -> list[str]:
    cases = CASE_KINDS[:]
    while len(cases) < row_count:
        cases.append(rng.choice(CASE_KINDS))
    rng.shuffle(cases)
    return cases[:row_count]


def _build_case_payload(case_kind: str, expected_model: str, rng: random.Random) -> CasePayload:
    if case_kind == "exact_single":
        return {"status_code": 200, "kind": "json", "models": [expected_model], "delay_seconds": 0.0}

    if case_kind == "exact_many":
        models = _build_models_with_expected(rng, expected_model, rng.randint(1, 4))
        return {"status_code": 200, "kind": "json", "models": models, "delay_seconds": 0.0}

    if case_kind == "empty":
        return {"status_code": 200, "kind": "json", "models": [], "delay_seconds": 0.0}

    if case_kind == "extra_single":
        models = _build_models_with_expected(rng, expected_model, 1)
        return {"status_code": 200, "kind": "json", "models": models, "delay_seconds": 0.0}

    if case_kind == "extra_many":
        models = _build_models_with_expected(rng, expected_model, rng.randint(2, 5))
        return {"status_code": 200, "kind": "json", "models": models, "delay_seconds": 0.0}

    if case_kind == "both_single":
        models = _unique_models(rng, "other", 1, [expected_model])
        return {"status_code": 200, "kind": "json", "models": models, "delay_seconds": 0.0}

    if case_kind == "both_many":
        models = _unique_models(rng, "other", rng.randint(2, 5), [expected_model])
        return {"status_code": 200, "kind": "json", "models": models, "delay_seconds": 0.0}

    if case_kind == "invalid_json":
        return {"status_code": 200, "kind": "invalid_json", "message": "not-json", "delay_seconds": 0.0}

    if case_kind == "http_500":
        return {"status_code": 500, "kind": "error", "message": "mock upstream failure", "delay_seconds": 0.0}

    if case_kind == "timeout":
        return {"status_code": 200, "kind": "json", "models": [expected_model], "delay_seconds": 11.5}

    raise ValueError(f"Unknown case kind: {case_kind}")


def _send_response(handler: BaseHTTPRequestHandler, status_code: int, content_type: str, body: bytes) -> None:
    handler.send_response(status_code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_json(handler: BaseHTTPRequestHandler, status_code: int, payload: Mapping[str, object]) -> None:
    _send_response(
        handler,
        status_code,
        JSON_CONTENT_TYPE,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _send_text(handler: BaseHTTPRequestHandler, status_code: int, body: str) -> None:
    _send_response(handler, status_code, TEXT_CONTENT_TYPE, body.encode("utf-8"))


def _payload_float(payload: Mapping[str, object], key: str, default: float) -> float:
    value = payload.get(key, default)
    return float(value) if isinstance(value, (int, float)) else default


def _payload_int(payload: Mapping[str, object], key: str, default: int) -> int:
    value = payload.get(key, default)
    return value if isinstance(value, int) else default


def _payload_str(payload: Mapping[str, object], key: str, default: str) -> str:
    value = payload.get(key, default)
    return value if isinstance(value, str) else default


def _parse_case_payload(raw_payload: Mapping[str, object]) -> CasePayload:
    payload: CasePayload = {}

    case_kind = raw_payload.get("case_kind")
    if isinstance(case_kind, str):
        payload["case_kind"] = case_kind

    status_code = raw_payload.get("status_code")
    if isinstance(status_code, int):
        payload["status_code"] = status_code

    kind = raw_payload.get("kind")
    if isinstance(kind, str):
        payload["kind"] = kind

    models = raw_payload.get("models")
    if isinstance(models, list):
        string_models = cast(list[object], models)
        if all(isinstance(model, str) for model in string_models):
            payload["models"] = cast(list[str], string_models)

    delay_seconds = raw_payload.get("delay_seconds")
    if isinstance(delay_seconds, (int, float)):
        payload["delay_seconds"] = float(delay_seconds)

    message = raw_payload.get("message")
    if isinstance(message, str):
        payload["message"] = message

    return payload


def _load_manifest(manifest_path: Path) -> ManifestMap:
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_manifest, dict):
        raise ValueError("manifest must be a JSON object")

    manifest: ManifestMap = {}
    for case_id, raw_payload in cast(dict[str, object], raw_manifest).items():
        if not isinstance(raw_payload, dict):
            raise ValueError("manifest entries must be JSON objects keyed by string case ids")

        manifest[case_id] = _parse_case_payload(cast(Mapping[str, object], raw_payload))

    return manifest


def generate_fixtures(output_dir: Path, row_count: int, seed: int) -> Path:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "mock_input.csv"
    manifest_path = output_dir / "mock_manifest.json"
    settings_path = Path.cwd() / "settings.json"

    rows = _case_sequence(row_count, rng)
    manifest: ManifestMap = {}

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()

        for index, case_kind in enumerate(rows):
            case_id = f"case-{index:04d}"
            expected_model = f"model-{index:04d}"
            port = 30_000 + index
            call_method = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/{case_id}/chat/completions"
            payload = _build_case_payload(case_kind, expected_model, rng)

            manifest[case_id] = {
                "case_kind": case_kind,
                **payload,
            }

            writer.writerow(
                {
                    "port": port,
                    "modelID": expected_model,
                    "模型名": f"{expected_model}-name",
                    "监控id": f"monitor-{index:04d}",
                    "GPU型号": rng.choice(["A100", "H100", "L40", "RTX6000", "A800"]),
                    "GPU数量": rng.randint(1, 8),
                    "上下文长度（K）": rng.choice([4, 8, 16, 32, 64, 128]),
                    "容器名": f"container-{index:04d}",
                    "调用方法": call_method,
                }
            )

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    settings_payload: SettingsPayload = {
        "xlsx": {
            "input_path": "output/ci-fixtures/mock_input.xlsx",
            "input_sheet_name": "Sheet1",
        },
        "csv": {
            "input_path": "output/ci-fixtures/mock_input.csv",
            "output_path": "output/ci-fixtures/results",
        },
        "source": {
            "last_type": "csv",
        },
        "end_flag": {
            "tag": "__no_such_field__",
            "value": "__stop__",
        },
        "pass_port": [],
    }
    settings_path.write_text(json.dumps(settings_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return manifest_path


def _build_handler(manifest: ManifestMap) -> type[BaseHTTPRequestHandler]:
    class MockVllmHandler(BaseHTTPRequestHandler):
        manifest_map: ClassVar[ManifestMap] = manifest

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            request_path = urlsplit(self.path).path
            normalized_path = PurePosixPath(request_path)

            if normalized_path.name != "models":
                _send_json(self, 404, {"error": "not found"})
                return

            case_id = normalized_path.parent.name
            payload = self.manifest_map.get(case_id)
            if payload is None:
                _send_json(self, 404, {"error": "unknown case"})
                return

            delay_seconds = _payload_float(payload, "delay_seconds", 0.0)
            if delay_seconds > 0.0:
                time.sleep(delay_seconds)

            status_code = _payload_int(payload, "status_code", 200)
            kind = _payload_str(payload, "kind", "json")

            if kind == "invalid_json":
                _send_text(self, status_code, "not-json")
                return

            if status_code != 200:
                message = _payload_str(payload, "message", "mock upstream failure")
                _send_json(self, status_code, {"error": message})
                return

            models = payload.get("models", [])

            response_body = {"data": [{"id": str(model)} for model in models]}
            _send_json(self, 200, response_body)

    return MockVllmHandler


def serve_manifest(manifest_path: Path, host: str, port: int) -> None:
    manifest = _load_manifest(manifest_path)
    handler = _build_handler(manifest)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Mock vLLM server listening on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and serve CI fixtures for AICheck.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate mock CSV, manifest, and settings.json")
    generate_parser.add_argument("--output", type=Path, required=True)
    generate_parser.add_argument("--rows", type=int, default=1000)
    generate_parser.add_argument("--seed", type=int, default=42)

    serve_parser = subparsers.add_parser("serve", help="Serve the generated manifest as a mock vLLM endpoint")
    serve_parser.add_argument("--manifest", type=Path, required=True)
    serve_parser.add_argument("--host", default=DEFAULT_HOST)
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = parser.parse_args()

    if args.command == "generate":
        generate_fixtures(args.output, args.rows, args.seed)
        return

    if args.command == "serve":
        serve_manifest(args.manifest, args.host, args.port)
        return

    raise AssertionError("unreachable")


if __name__ == "__main__":
    main()