"""Idempotent paper-project projections; immutable study evidence stays in place.

The caller supplies a controller-derived snapshot. Project location is bound by
the initial delegation, never accepted as an arbitrary model-proposed edit.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .common import require, safe_path, locked, read_json, write_json, timestamp


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _child(root, relative):
    candidate = root / relative
    require(candidate.is_relative_to(root), '投影路径越出项目')
    for part in [candidate, *candidate.parents]:
        if part == root.parent:
            break
        require(not part.is_symlink() and not (hasattr(part, 'is_junction') and part.is_junction()),
                '项目投影拒绝符号链接或junction')
    resolved = safe_path(candidate)
    require(resolved.is_relative_to(root), '投影路径越出项目')
    return resolved


def _atomic_text(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)


def _replace_block(text, key, content):
    start, end = '<!-- medexp:' + key + ':begin -->', '<!-- medexp:' + key + ':end -->'
    block = start + '\n' + content.rstrip() + '\n' + end
    pattern = re.escape(start) + r'.*?' + re.escape(end)
    require((start in text) == (end in text), '现有投影标记不完整，先核对文档')
    if start in text:
        return re.sub(pattern, lambda _: block, text, count=1, flags=re.S)
    return text.rstrip() + '\n\n' + block + '\n'


def _section(text, title, key, content):
    header = '## ' + title
    matches = list(re.finditer(r'^##\s+(.+)$', text, re.M))
    for index, match in enumerate(matches):
        if match.group(1).strip() == title:
            stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            section = text[match.end():stop]
            replacement = _replace_block(section, key, content)
            return text[:match.end()] + '\n' + replacement + '\n' + text[stop:]
    return text.rstrip() + '\n\n' + header + '\n\n' + _replace_block('', key, content)


def _supersede(section, key, content):
    marker = '<!-- medexp:history:' + key + ':begin -->'
    if marker in section:
        history = section[section.index(marker):]
    else:
        history = (marker + '\n<details>\n<summary>初始确认参考，已被当前方案取代；固定目标仍见当前验收区</summary>\n\n'
                   + section.strip() + '\n\n</details>\n<!-- medexp:history:' + key + ':end -->\n')
    return _replace_block('', key, content) + '\n\n' + history


def _method_body(body, method, snap):
    if not method:
        return body
    # A structured response can contain a JSON-encoded method narrative. Render
    # its actual content as readable Markdown without changing the raw proposal.
    try:
        structured=json.loads(method)
    except (ValueError,TypeError):
        structured=None
    if isinstance(structured,dict):
        titles={'implementation':'当前方法与技术路线','formal_training':'正式训练',
                'screening':'筛选与晋级','fixed_evaluation':'固定评价',
                'recovery':'故障恢复','budget_and_decisions':'预算与决策',
                'evidence_boundary':'证据边界','hypothesis':'当前方法假设',
                'technical_route':'技术路线','diagnosis':'诊断依据'}
        metadata={'candidate_id','commit','change_kind','classification_basis','artifacts_read'}
        parts=[]
        for key,value in structured.items():
            if key in metadata:continue
            rendered=value if isinstance(value,str) else '```json\n'+_json(value)+'\n```'
            parts.append('### '+titles.get(key,key)+'\n\n'+rendered)
        if parts:method='\n\n'.join(parts)
    # Model-authored headings belong inside a host plan section. Letting them
    # become sibling H1/H2 sections would strand old text at the next update.
    method = re.sub(r'^#{1,2}(?=\s)', '###', method, flags=re.M)
    headings = list(re.finditer(r'^##\s+(.+)$', body, re.M))
    replacements = []
    found_method = False
    fixed = {'scientific_contract': {k:v for k,v in snap.get('confirmed_contract',{}).items()
                                    if k in ('task','data','primary_metric','guard_metrics','verification','matrix')},
             'fixed_rules': snap.get('confirmed_rules',{})}
    for index, heading in enumerate(headings):
        title = heading.group(1)
        stop = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        section = body[heading.end():stop]
        key, content = None, None
        if re.search(r'方法|技术路线|技术方案|\bmethods?\b|technical (?:approach|route)',
                     title, re.I):
            key, content = 'route', method.strip()
            found_method = True
        elif re.match(r'4[.、\s]',title) and re.search(r'实验|分析设计',title) or re.search(r'experiment(?:al)? design',title,re.I):
            key, content = 'design', ('### 当前实验设计与固定验收\n\n'
                '以下固定科学目标、贡献命题/反证/边界和统计规则继续有效；方法实现变化不能删除它们。\n```json\n'
                + _json(fixed) + '\n```\n\n当前完整命令（初筛与正式区分）：\n```json\n'
                + _json(snap.get('current_commands',[])) + '\n```\n\n资源余额：\n```json\n'
                + _json(snap.get('budgets',{})) + '\n```')
        elif re.match(r'8[.、\s]',title) and re.search(r'一致性|冲突',title):
            key, content = 'consistency', ('### 当前主张与证据\n\n固定贡献目标仍全部有效，未被有效正式结果支持前不声称成立。\n```json\n'
                + _json({'fixed_contribution_goals':snap.get('confirmed_rules',{}).get('required_contributions',[]),
                         'diagnosis':snap.get('diagnosis'),'valid_results':snap.get('valid_results',[]),
                         'final_selection':snap.get('final_selection')}) + '\n```')
        elif re.match(r'9[.、\s]',title) and re.search(r'工程|实施|agent',title,re.I) or re.search(r'next steps|^next\b',title,re.I):
            key, content = 'tasks', ('### 当前工程任务与停止条件\n\n'
                + '\n'.join('- '+str(x) for x in snap.get('next_steps',[]))
                + '\n\n```json\n' + _json({'latest_attempt':snap.get('latest_attempt',{}),
                    'budgets':snap.get('budgets',{}),'test_state':snap.get('test_state',{})}) + '\n```')
        if key:
            if key == 'route':
                content += ('\n\n### 固定科学目标（持续有效）\n```json\n' + _json(fixed) + '\n```')
            replacements.append((heading.end(),stop,'\n\n'+_supersede(section,key,content)+'\n\n'))
    for start, stop, replacement in reversed(replacements):
        body=body[:start]+replacement+body[stop:]
    if not found_method:
        body=body.rstrip()+'\n\n## 当前方法与技术路线\n\n'+method.strip()+'\n\n固定目标：\n```json\n'+_json(fixed)+'\n```\n'
    return body


def _invalidate_rows(text, affected):
    if not affected:
        return text
    columns = None
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.lstrip().startswith('|'):
            columns = None
            continue
        cells = [part.strip() for part in line.strip().split('|')[1:-1]]
        if '状态' in cells and '阶段' in cells:
            columns = (cells.index('阶段'), cells.index('状态'), cells.index('#') if '#' in cells else None)
            continue
        if not columns or len(cells) <= max(i for i in columns if i is not None):
            continue
        stage, status, number = columns
        if cells[stage] in affected or (number is not None and cells[number] in affected):
            if cells[status] in ('已确认', '待确认', '进行中', '完成'):
                cells[status] = '需返工'
                lines[index] = '| ' + ' | '.join(cells) + ' |\n'
    return ''.join(lines)


def _render(project, study, snap):
    plan_path = _child(project, '00_plan/project-plan.md')
    if snap.get('plan_markdown'):
        body = snap['plan_markdown']
        require(isinstance(body, str) and body.strip(), '当前计划必须为非空Markdown')
    elif plan_path.exists():
        body = plan_path.read_text(encoding='utf-8')
    else:
        original = _child(study, 'plans/original.md')
        require(original.is_file(), '没有原计划，不能凭空编造科研计划')
        body = original.read_text(encoding='utf-8')
    body = re.sub(r'<!-- medexp:current-status:begin -->.*?<!-- medexp:current-status:end -->\s*',
                  '', body, flags=re.S)
    if not snap.get('plan_markdown'):
        body = _method_body(body, snap.get('method_plan'), snap)
    method = snap.get('current_method', '见当前方法章节')
    status = '\n'.join([
        '## 当前执行状态（受管证据投影）',
        '- 事件：' + snap['event_id'],
        '- 方法版本：' + str(snap.get('method_revision', '未知')),
        '- 阶段/状态：' + str(snap.get('stage', '未知')) + ' / ' + str(snap.get('status', '未知')),
        '- 当前方法：' + (method if isinstance(method, str) else _json(method)),
        '- 本次诊断：' + str(snap.get('diagnosis', '尚无新增诊断')),
        '- 本节为执行状态，不构成新的作者确认或科学有效性证明。',
        '\n### 最新尝试\n```json\n' + _json(snap.get('latest_attempt', {})) + '\n```',
        '\n### 当前有效结果（保留来源版本）\n```json\n' + _json(snap.get('valid_results', [])) + '\n```',
        '\n### 最终冻结方案\n```json\n' + _json(snap.get('final_selection')) + '\n```',
        '\n### 累计资源与测试状态\n```json\n' + _json({'budgets': snap.get('budgets', {}), 'test': snap.get('test_state', {})}) + '\n```',
        '\n### 下一步\n' + '\n'.join('- ' + str(item) for item in snap.get('next_steps', []))])
    current_plan = _replace_block(body, 'current-status', status)
    key = _digest(str(study).encode('utf-8'))[:16]
    location = str(study.relative_to(project)).replace('\\', '/') if study.is_relative_to(project) else str(study)
    index_path = _child(project, '01_analysis/README.md')
    index = index_path.read_text(encoding='utf-8') if index_path.exists() else '# 实验代码与结果总索引\n'
    details = '\n'.join([
        '### study：' + study.name,
        '- 受管目录：`' + location + '`；原始运行证据保留原位。',
        '- 报告：`' + location + '/report.md`',
        '- 当前计划：`00_plan/project-plan.md`；方法版本：' + str(snap.get('method_revision', '未知')),
        '- 事件/状态：' + snap['event_id'] + ' / ' + str(snap.get('status', '未知')),
        '- 最新尝试：' + _json(snap.get('latest_attempt', {})),
        '- 当前有效结果：' + _json(snap.get('valid_results', [])),
        '- 最终冻结方案：' + _json(snap.get('final_selection')),
        '- 锁定测试状态：' + _json(snap.get('test_state', {}))])
    current_index = _replace_block(index, key, details)
    project_path = _child(project, 'PROJECT.md')
    project_text = project_path.read_text(encoding='utf-8')
    project_text = _invalidate_rows(project_text, set(str(x) for x in snap.get('affected_stages', [])))
    project_text = _section(project_text, '目录说明', key,
                            '- 计划 `00_plan/project-plan.md`；study `' + location + '`；报告 `' + location +
                            '/report.md`；测试状态：' + _json(snap.get('test_state', {})))
    project_text = _section(project_text, '变更记录', key + '-' + _digest(snap['event_id'].encode())[:12],
                            '- ' + str(snap.get('archive_date', datetime.now().astimezone().date().isoformat())) +
                            ' 事件 ' + snap['event_id'] + '：方法版本 ' + str(snap.get('method_revision', '未知')) +
                            '，状态 ' + str(snap.get('status', '未知')) + '；旧版按归档回执追溯。')
    return {'00_plan/project-plan.md': current_plan, '01_analysis/README.md': current_index, 'PROJECT.md': project_text}


def sync_project(study_root, snapshot):
    study = safe_path(study_root)
    require(isinstance(snapshot, dict), '投影快照必须为对象')
    require(isinstance(snapshot.get('event_id'), str) and snapshot['event_id'].strip(), '缺少稳定事件身份')
    requested = snapshot.get('project_root')
    project = safe_path(requested) if requested else next((p for p in study.parents if (p / 'PROJECT.md').is_file()), None)
    if project is None:
        return {'synced': False, 'reason': 'no PROJECT.md; standalone study unchanged'}
    require(project != study and (project / 'PROJECT.md').is_file(), '项目根必须有独立的PROJECT.md')
    project = safe_path(project)
    _child(project, 'PROJECT.md')
    fingerprint = _digest(json.dumps(snapshot, ensure_ascii=False, allow_nan=False,
                                     sort_keys=True).encode('utf-8'))
    receipt_path = _child(study, 'evidence/projections/' + _digest(snapshot['event_id'].encode()) + '.json')
    head_path = _child(project, '_process/plan/medexp-projection-head.json')
    with locked(project):
        if receipt_path.exists():
            receipt = read_json(receipt_path)
            require(receipt['snapshot_sha256'] == fingerprint, '同一事件出现不同投影内容，先核对状态')
            require(receipt['project_root'] == str(project), '投影项目根变化，拒绝重放')
            if receipt['status'] == 'applied':
                for item in receipt['documents']:
                    if item['archive']:
                        archived = _child(project,item['archive'])
                        require(archived.is_file() and _digest(archived.read_bytes())==item['before_sha256'],
                                '已应用事件的归档缺失或损坏：'+item['relative'])
                require(head_path.is_file(), '投影当前身份回执缺失，先核对状态')
                head = read_json(head_path)
                for item in head['documents']:
                    target=_child(project,item['relative'])
                    require(target.is_file() and _digest(target.read_bytes())==item['after_sha256'],
                            '当前投影文档已被外部修改，先核对状态：'+item['relative'])
                return {'synced': True, 'receipt': str(receipt_path), 'replayed': True,
                        'files': [str(project/p['relative']) for p in receipt['documents']]}
        else:
            documents = _render(project, study, snapshot)
            date = snapshot.get('archive_date', datetime.now().astimezone().date().isoformat())
            require(isinstance(date, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date), '归档日期格式无效')
            datetime.fromisoformat(date)
            batch, count = date, 1
            while any(_child(project, '_archive/' + batch + '/' + relative).exists() for relative in documents):
                count += 1
                batch = date + '_' + str(count)
            items = []
            for relative, content in documents.items():
                target = _child(project, relative)
                previous = target.read_bytes() if target.exists() else None
                items.append({'relative': relative, 'content': content,
                              'before_sha256': _digest(previous) if previous is not None else None,
                              'after_sha256': _digest(content.encode('utf-8')),
                              'archive': '_archive/' + batch + '/' + relative if previous is not None else None})
            receipt = {'status': 'prepared', 'event_id': snapshot['event_id'], 'snapshot_sha256': fingerprint,
                       'project_root': str(project), 'prepared_at': timestamp(), 'documents': items}
            write_json(receipt_path, receipt)
        for item in receipt['documents']:
            target = _child(project, item['relative'])
            current = target.read_bytes() if target.exists() else None
            current_hash = _digest(current) if current is not None else None
            published = current_hash == item['after_sha256']
            require(published or current_hash == item['before_sha256'], '待同步文档已被其他工具修改，拒绝覆盖：' + item['relative'])
            if item['archive']:
                archived = _child(project, item['archive'])
                archived.parent.mkdir(parents=True, exist_ok=True)
                if archived.exists():
                    require(_digest(archived.read_bytes()) == item['before_sha256'], '归档内容不符')
                else:
                    require(not published, '已发布文档的原归档缺失，无法安全重建：'+item['relative'])
                    with archived.open('xb') as stream:
                        stream.write(current)
                        stream.flush()
                        os.fsync(stream.fileno())
            if not published:
                _atomic_text(target, item['content'])
        write_json(head_path, {'event_id':receipt['event_id'], 'receipt':str(receipt_path),
                              'documents':[{k:item[k] for k in ('relative','after_sha256')} for item in receipt['documents']]})
        receipt['status'] = 'applied'
        receipt['applied_at'] = timestamp()
        write_json(receipt_path, receipt)
    return {'synced': True, 'receipt': str(receipt_path), 'replayed': False,
            'files': [str(project/p['relative']) for p in receipt['documents']],
            'archives': [str(project/p['archive']) for p in receipt['documents'] if p['archive']]}
