"""Mechanical checks only: never asserts author approval, Word acceptance or readiness."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import zipfile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
KINDS = {"manuscript", "title_page", "statements", "cover_letter", "checklist",
         "figure", "attachment", "changes", "requirements", "pending"}
EXTENSIONS = {".docx", ".pdf", ".md", ".txt", ".tif", ".tiff", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".xlsx"}
PRIVATE_PARTS = {"_process", "_archive", "evidence", "sources", "private", "raw", "consent", "credentials", "logs"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _text(value):
    # Ignore run/paragraph boundaries and ordinary typography, preserve reference content.
    table = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).translate(table))


def _field(instruction, display):
    if "ZOTERO" not in instruction.upper():
        return None
    if re.match(r"\s*ADDIN\s+ZOTERO_ITEM\s+CSL_CITATION\s*\{", instruction):
        kind = "citation"
    elif re.match(r"\s*ADDIN\s+ZOTERO_BIBL\s*\{", instruction):
        kind = "bibliography"
    else:
        raise ValueError("unsupported Zotero instruction")
    try:
        encoded = instruction[instruction.index("{"):]
        payload, end = json.JSONDecoder().raw_decode(encoded)
        tail = encoded[end:]
    except (ValueError, TypeError) as exc:
        raise ValueError("unsupported malformed Zotero JSON") from exc
    expected_tail = "CSL_BIBLIOGRAPHY" if kind == "bibliography" else ""
    if tail.strip() != expected_tail or not isinstance(payload, dict):
        raise ValueError("unsupported Zotero field suffix/payload")
    if kind == "bibliography":
        return kind, {"data": payload, "display": _text(display)}
    items = payload.get("citationItems")
    if not isinstance(items, list) or not items:
        raise ValueError("unsupported empty/missing citationItems")
    identities = []
    for item in items:
        if not isinstance(item, dict) or "id" not in item or not isinstance(item.get("uris"), list) or not item["uris"]:
            raise ValueError("unsupported citation identity without id/uris")
        # Preserve every item property including key, locator and embedded metadata;
        # top-level style-specific formatted caches are intentionally excluded.
        identities.append(item)
    return kind, {"citation_id": payload.get("citationID"), "items": identities, "cached_display": display}


def _part(xml):
    root = ET.fromstring(xml)
    revision_tags = {W + name for name in ("del", "moveFrom", "ins", "moveTo")}
    revised_nodes = {child for node in root.iter() if node.tag in revision_tags for child in node.iter()}
    for node in root.iter():
        if node.tag.endswith("}instrText") and not node.tag.startswith(W) and "ZOTERO" in (node.text or "").upper():
            raise ValueError("unsupported OOXML namespace for Zotero field")
    stack, fields = [], []
    for node in root.iter():
        if stack and node in revised_nodes:
            stack[-1]["revised"] = True
        if node.tag == W + "fldSimple" and "ZOTERO" in node.get(W + "instr", "").upper():
            raise ValueError("unsupported simple Zotero field; complex fields required")
        if node.tag == W + "fldChar":
            op = node.get(W + "fldCharType")
            if op == "begin":
                if stack:
                    stack[-1]["has_child"] = True
                stack.append({"instruction": "", "display": "", "result": False, "nested": bool(stack), "has_child": False, "revised": node in revised_nodes})
            elif op == "separate":
                if not stack:
                    raise ValueError("unsupported unmatched field separator")
                stack[-1]["result"] = True
            elif op == "end":
                if not stack:
                    raise ValueError("unsupported unmatched field end")
                current = stack.pop()
                parsed = _field(current["instruction"], current["display"])
                if parsed:
                    if current["revised"]:
                        raise ValueError("unsupported tracked revision affecting Zotero field")
                    if current["nested"] or current["has_child"] or not current["result"]:
                        raise ValueError("unsupported nested/incomplete Zotero field")
                    fields.append(parsed)
                if stack and parsed:
                    raise ValueError("unsupported nested Zotero field")
        elif node.tag == W + "instrText":
            if not stack:
                if "ZOTERO" in (node.text or "").upper():
                    raise ValueError("unsupported orphan Zotero instruction")
            elif not stack[-1]["result"]:
                stack[-1]["instruction"] += node.text or ""
        elif node.tag == W + "t" and stack and stack[-1]["result"]:
            stack[-1]["display"] += node.text or ""
    if stack:
        raise ValueError("unsupported unclosed complex field")
    return {"citations": [v for k, v in fields if k == "citation"],
            "bibliographies": [v for k, v in fields if k == "bibliography"],
            "order": [k for k, _ in fields]}


def snapshot(path):
    """Read all Word XML stories, joining split instructions; reject partial support."""
    parts, displays = {}, {}
    with zipfile.ZipFile(path) as archive:
        if "word/document.xml" not in archive.namelist():
            raise ValueError("missing word/document.xml")
        for name in sorted(archive.namelist()):
            if name.startswith("word/") and name.endswith(".xml"):
                parsed = _part(archive.read(name))
                if parsed["order"]:
                    displays[name] = [c.pop("cached_display") for c in parsed["citations"]]
                    parts[name] = parsed
    return {"schema": 1, "sha256": digest(path), "parts": parts, "citation_displays": displays,
            "scope": "complex Zotero OOXML identity/order and bibliography cache; not Word/Refresh or scientific validation"}


def compare(baseline, source, candidate):
    errors = []
    if baseline.get("schema") != 1 or "parts" not in baseline or "sha256" not in baseline:
        raise ValueError("unsupported baseline schema")
    if digest(source) != baseline["sha256"]:
        errors.append("source_hash_changed")
    result = snapshot(candidate)
    if baseline["parts"] != result["parts"]:
        errors.append("zotero_identity_order_or_bibliography_changed")
    return {"ok": not errors, "errors": errors, "candidate_sha256": result["sha256"], "scope": result["scope"]}


def _nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def _http_url(value):
    if not _nonblank(value) or any(ch.isspace() for ch in value):
        return False
    try:
        parsed = urlparse(value)
        # Accessing port also detects malformed brackets/ports; no network lookup.
        port = parsed.port
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            return False
        if ":" in host:
            import ipaddress
            ipaddress.IPv6Address(host)
            return True
        ascii_host = host.encode("idna").decode("ascii").rstrip(".")
        return bool(ascii_host) and len(ascii_host) <= 253 and all(
            re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
            for label in ascii_host.split("."))
    except (ValueError, UnicodeError):
        return False


def assess(record):
    """Audit supplied records; evidence strings require human review, never self-authenticate."""
    gaps = []
    facts, requirements = record.get("facts", []), record.get("requirements", [])
    if not facts:
        gaps.append("fact_inventory_missing")
    for fact in facts:
        if not fact.get("required", True):
            continue
        confirmation = fact.get("confirmation")
        value = fact.get("value")
        missing = value is None or (isinstance(value, str) and not value.strip()) or value == [] or value == {}
        prefix = "fact_unresolved:" + str(fact.get("name", "unnamed")) + ":"
        if missing:
            gaps.append(prefix + "value")
        if not _nonblank(fact.get("source")):
            gaps.append(prefix + "source")
        if not isinstance(confirmation, dict):
            gaps.append(prefix + "confirmation")
        else:
            for key in ("by", "evidence"):
                if not _nonblank(confirmation.get(key)):
                    gaps.append(prefix + key)
    if not requirements:
        gaps.append("official_requirements_missing")
    for rule in requirements:
        try:
            datetime.date.fromisoformat(rule.get("access_date", ""))
            valid_date = True
        except (ValueError, TypeError):
            valid_date = False
        if not _http_url(rule.get("url")):
            gaps.append("requirement_unresolved:" + str(rule.get("name", "unnamed")) + ":url")
        if (not valid_date or rule.get("provenance") != "official"
                or rule.get("verification") not in {"current", "supplied_official"}
                or rule.get("resolved") is not True):
            gaps.append("requirement_unresolved:" + str(rule.get("name", "unnamed")))
    gaps.extend("conflict:" + str(c) for c in record.get("conflicts", []))
    checks = record.get("checks", {})
    for key in ("preservation", "visual", "word_refresh"):
        allowed = {"pass", "not_applicable"} if key == "word_refresh" else {"pass"}
        if checks.get(key) not in allowed:
            gaps.append("acceptance_missing:" + key)
    return {"status": "draft" if gaps else "pending_author", "gaps": gaps,
            "scope": "record completeness only; facts, source authority and human approval are not authenticated"}


def package(root, entries, output):
    """Create a new ZIP from explicit relative artifact records, never recursive discovery."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("refusing to overwrite existing package")
    checked, seen = [], set()
    for entry in entries:
        rel = PurePosixPath(entry["path"])
        if (entry.get("kind") not in KINDS or rel.is_absolute() or ".." in rel.parts
                or "\\" in entry["path"] or ":" in entry["path"] or not rel.parts
                or any(p.lower() in PRIVATE_PARTS for p in rel.parts)
                or rel.suffix.lower() not in EXTENSIONS or rel.as_posix().lower() in seen):
            raise ValueError("non-submission or unsafe artifact: " + str(rel))
        path = root.joinpath(*rel.parts)
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file() or not path.resolve().is_relative_to(root) or path.resolve() == output:
            raise ValueError("artifact must be a regular file within deliverables: " + str(rel))
        seen.add(rel.as_posix().lower())
        checked.append((path, rel.as_posix()))
    if not checked:
        raise ValueError("empty artifact allowlist")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, rel in checked:
            archive.write(path, rel)
    return [rel for _, rel in checked]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="Print source hash and protected field baseline JSON")
    snap.add_argument("source", type=Path)
    check = commands.add_parser("compare", help="Check source immutability and adapted DOCX fields")
    check.add_argument("baseline", type=Path)
    check.add_argument("source", type=Path)
    check.add_argument("candidate", type=Path)
    audit = commands.add_parser("assess", help="Audit preparation record; never approves submission")
    audit.add_argument("record", type=Path)
    pack = commands.add_parser("package", help="ZIP explicit artifact allowlist into a new path")
    pack.add_argument("root", type=Path)
    pack.add_argument("allowlist", type=Path)
    pack.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        read = lambda p: json.loads(p.read_text(encoding="utf-8-sig"))
        if args.command == "snapshot":
            result = snapshot(args.source)
        elif args.command == "compare":
            result = compare(read(args.baseline), args.source, args.candidate)
        elif args.command == "assess":
            result = assess(read(args.record))
        else:
            result = {"artifacts": package(args.root, read(args.allowlist), args.output)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result.get("ok") is False or result.get("status") == "draft")
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
