"""Create one draft figure entry without replacing any existing entry."""
import argparse
import os
from pathlib import Path
import re
import shutil
import tempfile

from PIL import Image
from common import cli_error, json_bytes, load_config, read_json, reject_links, sha256, slug, utc_now

CODE_PROVENANCE = ('original_runs', 'adapted', 'archived_only', 'reconstructed', 'example_not_target')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gallery', type=Path, required=True)
    parser.add_argument('--post-slug', required=True)
    parser.add_argument('--fig-id', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--post-title')
    parser.add_argument('--post-url')
    parser.add_argument('--account')
    parser.add_argument('--author')
    parser.add_argument('--publish-date')
    parser.add_argument('--scenario', action='append')
    parser.add_argument('--secondary-scenario', action='append', default=[])
    parser.add_argument('--free-tag', action='append', default=[])
    parser.add_argument('--language', choices=('python', 'r', 'unknown'), default='unknown')
    parser.add_argument('--label', default='')
    parser.add_argument('--caption', default='')
    parser.add_argument('--panel', action='append', default=[])
    parser.add_argument('--chart-type', action='append', default=[])
    parser.add_argument('--data-provenance', choices=('original', 'estimated', 'synthetic', 'mixed'), default='estimated')
    parser.add_argument('--code-provenance', choices=CODE_PROVENANCE, default='reconstructed')
    parser.add_argument('--original-code-provenance', choices=CODE_PROVENANCE)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args(argv)
    stage = None
    try:
        load_config(args.config)
        slug(args.post_slug)
        slug(args.fig_id)
        match = re.fullmatch(r'fig(\d+)(?:-[a-z0-9]+)*', args.fig_id)
        if not match or int(match[1]) < 1:
            raise ValueError('--fig-id must start with figNN, index >= 1')
        gallery = reject_links(args.gallery)
        target = reject_links(gallery / args.post_slug / 'figures' / args.fig_id)
        if target.exists():
            raise ValueError(f'Entry exists: {target}; use dedupe --dry-run before updating')
        with Image.open(args.source) as image:
            image.load()
            size = list(image.size)
            if image.format != 'PNG':
                raise ValueError('T1 entry source must be PNG; preserve original bytes')
        source_meta = args.source.parent / 'meta.json'
        post_meta = gallery / args.post_slug / 'meta.json'
        post = read_json(post_meta) if post_meta.exists() else read_json(source_meta) if source_meta.exists() else {}
        taxonomy = read_json(Path(__file__).resolve().parents[1] / 'assets/scenario_taxonomy.yaml')
        scenarios = args.scenario or ['other']
        if not 1 <= len(scenarios) <= 2 or len(set(scenarios)) != len(scenarios) or any(s not in taxonomy['scenarios'] for s in scenarios):
            raise ValueError('Select 1-2 controlled --scenario values from scenario_taxonomy.yaml')
        secondary = list(dict.fromkeys(args.secondary_scenario))
        if any(s not in taxonomy['scenarios'] for s in secondary):
            raise ValueError('Select controlled --secondary-scenario values from scenario_taxonomy.yaml')
        free_tags = list(dict.fromkeys(tag.strip() for tag in args.free_tag))
        if any(not tag for tag in free_tags):
            raise ValueError('--free-tag must not be empty or whitespace')
        now = utc_now()
        meta = {
            'id': f'{args.post_slug}__{args.fig_id}',
            'post': {'title': args.post_title or post.get('title'), 'account': args.account or post.get('account'),
                     'author': args.author or post.get('author'),
                     'publish_date': args.publish_date or (post.get('publish_time') or '')[:10] or None,
                     'url': args.post_url or post.get('url')},
            'figure': {'index': int(match[1]), 'label': args.label, 'caption': args.caption,
                       'panels': args.panel, 'chart_types': args.chart_type, 'canvas_px': size},
            'scenarios': {'primary': scenarios, 'secondary': secondary, 'free': free_tags},
            'language': args.language, 'data_provenance': args.data_provenance, 'code_provenance': args.code_provenance,
            'original_code_provenance': args.original_code_provenance, 'files': {'source_image': f'source/fig{match[1]}.png'},
            'status': 'draft', 'version': 1, 'source_image_sha256': sha256(args.source),
            'created_at': now, 'updated_at': now,
        }
        # Defaults describe the planned reconstruction, not a claim of completed work.
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.entry-', dir=target.parent))
        for name in ('source', 'original_code', 'code', 'data', 'output', 'compare', 'history'):
            (stage / name).mkdir()
        shutil.copyfile(args.source, stage / meta['files']['source_image'])
        source_md = gallery / args.post_slug / 'source.md'
        if not source_md.exists():
            source_md = args.source.parent / 'source.md'
        if source_md.exists():
            shutil.copyfile(source_md, stage / 'source/source.md')
            meta['files']['source_text'] = 'source/source.md'
        (stage / 'meta.json').write_bytes(json_bytes(meta))
        (stage / 'README.md').write_text(
            f'# {meta["post"]["title"] or meta["id"]}\n\n'
            '状态：draft，尚未复刻或作者签核。\n\n'
            f'图号：{args.label or "待确认"}\n\n面板：{", ".join(args.panel) or "待确认"}\n\n'
            f'语言：{args.language}\n\n'
            '## 来源与数据\n原图及全文保留在 source/；数据来源待读图确认。estimated 为计划默认值，'
            '不表示已完成估读。记录列名、单位、行数、缺失值、uncertain_reason 与估读映射。\n\n'
            '## 代码与运行\n待填运行命令、Python/R 版本、依赖版本、实际字体、失败原因及改造差异。'
            '先判断帖子示例代码是否为目标图代码；不得把示例代码称为目标图生成代码。\n\n'
            '## QA 与签核\n待生成 PNG/PDF/SVG、thumb.png、compare/、qa_report.md；'
            '人工逐项检查后记录作者、日期与结论。\n\n## 历史\nhistory/ 保存旧版产物。\n', encoding='utf-8')
        os.rename(stage, target)  # On Windows an existing directory is never replaced.
        stage = None
        print(f'created {target} status=draft version=1')
        return 0
    except (OSError, ValueError) as error:
        return cli_error(error)
    finally:
        if stage is not None:
            shutil.rmtree(stage)


if __name__ == '__main__':
    raise SystemExit(main())
