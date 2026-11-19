"""Lightweight JSON CLI for co-evolving medical imaging experiments (v3)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from medexp.common import safe_path
from medexp import study


def _csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(',') if x.strip()]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='医学影像实验与计划书协同控制器（轻量 v3）')
    sub = parser.add_subparsers(dest='action', required=True)

    p_init = sub.add_parser('init', help='初始化课题并校验环境与轻量配置')
    p_init.add_argument('--root', required=True)
    p_init.add_argument('--config', required=True)
    p_init.add_argument('--authorization', default='')

    p_audit = sub.add_parser('audit', help='执行患者/分组划分防泄漏审计（训练前必过）')
    p_audit.add_argument('--root', required=True)

    p_run = sub.add_parser('run', help='执行单次受管训练并登记结果与耗时')
    p_run.add_argument('--root', required=True)
    p_run.add_argument('--entry', required=True)
    p_run.add_argument('--seed', type=int, required=True)
    p_run.add_argument('--phase', choices=('screening', 'formal'), default='formal')
    p_run.add_argument('--command-json', default=None)

    p_rev = sub.add_parser('revise', help='实验不理想时修订路线、实验条目并同步更新计划书')
    p_rev.add_argument('--root', required=True)
    p_rev.add_argument('--summary', required=True)
    p_rev.add_argument('--entries-json', default=None)
    p_rev.add_argument('--reference', default=None)
    p_rev.add_argument('--hypothesis', default=None)
    p_rev.add_argument('--plan-file', default=None)
    p_rev.add_argument('--reusable-entries', default='')
    p_rev.add_argument('--invalidate-entries', default='')

    p_status = sub.add_parser('status', help='查看当前路线、预算余额、有效验证结果与测试状态')
    p_status.add_argument('--root', required=True)

    p_chk = sub.add_parser('pretest-check', help='冻结测试前登记一次独立只读核查')
    p_chk.add_argument('--root', required=True)
    p_chk.add_argument('--reviewer', required=True)
    p_chk.add_argument('--verdict', choices=('pass', 'block'), required=True)
    p_chk.add_argument('--summary', required=True)
    p_chk.add_argument('--checked-files', default='')

    p_frz = sub.add_parser('freeze', help='作者选定最终路线并冻结条目（此后禁止继续探索）')
    p_frz.add_argument('--root', required=True)
    p_frz.add_argument('--entries', required=True)
    p_frz.add_argument('--statement', required=True)

    p_test = sub.add_parser('test', help='对已冻结条目执行锁定测试集评估（仅报告，不回流选型）')
    p_test.add_argument('--root', required=True)
    p_test.add_argument('--entry', required=True)
    p_test.add_argument('--rationale', default='冻结最终路线后统一评估锁定测试集')

    p_fin = sub.add_parser('finalize', help='定稿收口：保留唯一干净最终路线计划书并生成终版报告')
    p_fin.add_argument('--root', required=True)
    p_fin.add_argument('--plan-file', default=None)
    p_fin.add_argument('--no-rework', action='store_true')

    p_exp = sub.add_parser('export', help='导出 report.md 与 report.json')
    p_exp.add_argument('--root', required=True)

    args = parser.parse_args(argv)
    try:
        root = safe_path(args.root)
        if args.action == 'init':
            res = study.init(root, Path(args.config), args.authorization)
        elif args.action == 'audit':
            res = study.audit(root)
        elif args.action == 'run':
            res = study.run_entry(
                root, args.entry, args.seed, args.phase,
                Path(args.command_json) if args.command_json else None,
            )
        elif args.action == 'revise':
            res = study.revise_route(
                root, args.summary,
                entries_json=Path(args.entries_json) if args.entries_json else None,
                reference=args.reference,
                hypothesis=args.hypothesis,
                plan_file=Path(args.plan_file) if args.plan_file else None,
                reusable_entries=_csv_list(args.reusable_entries),
                invalidate_entries=_csv_list(args.invalidate_entries),
            )
        elif args.action == 'status':
            res = study.status(root)
        elif args.action == 'pretest-check':
            res = study.pretest_check(root, args.reviewer, args.verdict, args.summary,
                                      _csv_list(args.checked_files))
        elif args.action == 'freeze':
            res = study.freeze(root, _csv_list(args.entries), args.statement)
        elif args.action == 'test':
            res = study.run_test(root, args.entry, args.rationale)
        elif args.action == 'finalize':
            res = study.finalize_study(root, Path(args.plan_file) if args.plan_file else None,
                                       mark_rework=not args.no_rework)
        else:
            res = study.export_report(root)
        print(json.dumps(res, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
