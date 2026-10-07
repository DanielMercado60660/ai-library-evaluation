"""Tests for the federated network seed manifest integrity."""

import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MANIFEST_PATH = DATA_DIR / "network_seed_manifest.json"

KNOWN_REGISTRY_CODES = {
    "mastodon-institute",
    "mammoth-valley",
    "ivory-university",
    "tusk-conservatory",
}


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _all_data_files() -> set[str]:
    """Return the set of catalog data file names that must be accounted for."""
    files = {f.name for f in DATA_DIR.glob("batch_*.json")}
    files.add("hanno_memorial_library_catalog.json")
    return files


def _collect_book_ids(manifest: dict) -> dict[str, list[str]]:
    """Collect book IDs per library from manifest sources."""
    result: dict[str, list[str]] = {}
    hub = manifest["hub"]
    hub_ids: list[str] = []
    for src in hub["sources"]:
        data = json.loads((DATA_DIR / src["file"]).read_text(encoding="utf-8"))
        hub_ids.extend(b["id"] for b in data.get(src["key"], []))
    result[hub["code"]] = hub_ids

    for spoke in manifest["spokes"]:
        ids: list[str] = []
        for src in spoke["sources"]:
            data = json.loads((DATA_DIR / src["file"]).read_text(encoding="utf-8"))
            ids.extend(b["id"] for b in data.get(src["key"], []))
        result[spoke["code"]] = ids
    return result


class TestFederatedSeedManifest:
    """Manifest schema validation and batch coverage integrity."""

    def test_manifest_file_exists(self):
        """network_seed_manifest.json exists in data/."""
        assert MANIFEST_PATH.exists(), f"Missing: {MANIFEST_PATH}"

    def test_manifest_schema_version_is_1_4(self):
        """schema_version is '1.4'."""
        manifest = _load_manifest()
        assert manifest["schema_version"] == "1.4"

    def test_manifest_hub_is_hanno(self):
        """Hub library is hanno-memorial."""
        manifest = _load_manifest()
        assert manifest["hub"]["code"] == "hanno-memorial"
        assert manifest["hub"]["name"] == "Hanno Memorial Library"

    def test_manifest_has_four_spokes(self):
        """Exactly 4 spoke libraries defined."""
        manifest = _load_manifest()
        assert len(manifest["spokes"]) == 4
        codes = {s["code"] for s in manifest["spokes"]}
        assert codes == KNOWN_REGISTRY_CODES

    def test_all_batch_files_assigned(self):
        """Every batch_*.json and main catalog appear in batch_coverage."""
        manifest = _load_manifest()
        coverage = set(manifest["batch_coverage"].keys())
        expected = _all_data_files()
        missing = expected - coverage
        assert not missing, f"Unassigned data files: {sorted(missing)}"

    def test_no_duplicate_batch_assignments(self):
        """No batch file assigned to more than one library's sources."""
        manifest = _load_manifest()
        all_sources: list[str] = []
        for src in manifest["hub"]["sources"]:
            all_sources.append(src["file"])
        for spoke in manifest["spokes"]:
            for src in spoke["sources"]:
                all_sources.append(src["file"])

        dupes = [f for f, count in Counter(all_sources).items() if count > 1]
        assert not dupes, f"Files in multiple libraries: {dupes}"

    def test_batch_source_counts_match_actual(self):
        """Declared counts match actual book counts in data files."""
        manifest = _load_manifest()
        errors: list[str] = []

        def _check(library_code: str, sources: list[dict]) -> None:
            for src in sources:
                data = json.loads((DATA_DIR / src["file"]).read_text(encoding="utf-8"))
                actual = len(data.get(src["key"], []))
                if actual != src["count"]:
                    errors.append(f"{library_code}/{src['file']}: declared {src['count']}, actual {actual}")

        _check(manifest["hub"]["code"], manifest["hub"]["sources"])
        for spoke in manifest["spokes"]:
            _check(spoke["code"], spoke["sources"])

        assert not errors, "\n".join(errors)

    def test_total_network_books_is_635(self):
        """Total across all libraries equals 635."""
        manifest = _load_manifest()
        total = manifest["hub"]["total_books"]
        for spoke in manifest["spokes"]:
            total += spoke["total_books"]
        assert total == 635
        assert manifest["total_network_books"] == 635

    def test_no_duplicate_book_ids_across_libraries(self):
        """No book ID appears in two different library partitions."""
        manifest = _load_manifest()
        all_ids = _collect_book_ids(manifest)

        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for lib_code, ids in all_ids.items():
            for book_id in ids:
                if book_id in seen:
                    duplicates.append(f"{book_id} in {seen[book_id]} and {lib_code}")
                else:
                    seen[book_id] = lib_code

        assert not duplicates, f"{len(duplicates)} duplicates: {duplicates[:5]}"

    def test_spoke_codes_match_registry(self):
        """All spoke codes are known registry partner codes."""
        manifest = _load_manifest()
        spoke_codes = {s["code"] for s in manifest["spokes"]}
        unknown = spoke_codes - KNOWN_REGISTRY_CODES
        assert not unknown, f"Unknown codes: {sorted(unknown)}"

    def test_spoke_specializations_nonempty(self):
        """Each spoke has at least one specialization."""
        manifest = _load_manifest()
        for spoke in manifest["spokes"]:
            assert len(spoke.get("specializations", [])) > 0, (
                f"{spoke['code']} has no specializations"
            )

    def test_manifest_round_trip_deterministic(self):
        """Loading and re-serializing the manifest produces identical output."""
        raw = MANIFEST_PATH.read_text(encoding="utf-8")
        manifest = json.loads(raw)
        reserialized = json.dumps(manifest, indent=2) + "\n"
        assert raw == reserialized, "Manifest is not in canonical JSON format"
