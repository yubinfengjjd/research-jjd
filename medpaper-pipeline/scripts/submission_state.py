"""Print migrated PROJECT text; never writes or infers author confirmation."""
import argparse
from pathlib import Path
import re

ROW = re.compile(r"^\|\s*(\d+)\s*\|")


def update(text, changed_stage=None, affects_main=True):
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if re.match(r"^\|\s*#\s*\|\s*阶段\s*\|", line)]
    if len(headers) != 1:
        raise ValueError("expected one PROJECT stage table")
    rows = {}
    for i in range(headers[0] + 1, len(lines)):
        if not lines[i].startswith("|"):
            break
        if match := ROW.match(lines[i]):
            stage = int(match.group(1))
            if stage in rows:
                raise ValueError("duplicate stage row")
            rows[stage] = i
    if 12 not in rows:
        raise ValueError("stage 12 missing; migrate reference stage first")
    if 13 not in rows:
        lines.insert(rows[12] + 1, "| 13 | 期刊适配与投稿材料准备 | medical-sci-submission | 未开始 | 06_submission/ | | | |")
        rows[13] = rows[12] + 1
    if affects_main and changed_stage is not None and 0 <= changed_stage < 13:
        targets = [13] + ([12] if changed_stage < 12 else [])
        for stage in targets:
            cells = lines[rows[stage]].split("|")
            if len(cells) != 10:
                raise ValueError("unexpected PROJECT stage table shape")
            if cells[4].strip() != "未开始":
                cells[4], cells[7] = " 需返工 ", " "
                lines[rows[stage]] = "|".join(cells)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--changed-stage", type=int, choices=range(14))
    parser.add_argument("--unaffected-main", action="store_true", help="Change does not affect manuscript/references")
    args = parser.parse_args(argv)
    try:
        print(update(args.project.read_text(encoding="utf-8-sig"), args.changed_stage, not args.unaffected_main), end="")
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
