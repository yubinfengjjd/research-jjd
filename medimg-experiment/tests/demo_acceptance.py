"""Run both modes (search, matrix) end to end on the split synthetic demo.

Usage: python tests/demo_acceptance.py <skill_dir> <python_exe> search|matrix
Review records here are acceptance-runner placeholders, not real independent reviews.
"""
import json, shutil, subprocess, sys, time, os
from pathlib import Path
import numpy

SK = Path(sys.argv[1]); PY = sys.argv[2]; MODE = sys.argv[3]
BASE = Path(os.environ['TEMP']) / 'medexp_demo_acceptance' / MODE
if BASE.exists():
    import stat
    shutil.rmtree(BASE, onexc=lambda f, x, e: (os.chmod(x, stat.S_IWRITE), f(x)))
BASE.mkdir(parents=True)
src = BASE / 'src'; shutil.copytree(SK / 'assets' / 'synthetic', src)
plan = BASE / 'plan.md'; plan.write_text('# synthetic plan\n', encoding='utf-8')
datadir = BASE / 'data'; datadir.mkdir(); (datadir / 'README').write_text('synthetic in code')
root = BASE / 'study'
ctl = [PY, str(SK / 'scripts' / 'controller.py')]


def call(*a, ok=True):
    r = subprocess.run(ctl + list(a), capture_output=True, text=True, encoding='utf-8')
    out = json.loads(r.stdout.strip().splitlines()[-1])
    print('>>', a[0], (a[4] if len(a) > 4 else ''), '->', out.get('status', out.get('error')), '|', out.get('summary_zh'))
    if ok and r.returncode:
        raise SystemExit('FAILED: ' + r.stdout + r.stderr)
    return out


c = json.loads((SK / 'assets' / 'contract-template.json').read_text(encoding='utf-8'))
frozen = ['synth_data.py', 'audit_split.py', 'evaluate_test.py']
c.update(study_id='e2e-' + MODE, task='classification', mode=MODE, hypothesis='wider MLP improves synthetic accuracy',
         plan_path=str(plan), stages=['baseline', 'explore', 'verify'] if MODE == 'search' else ['matrix'])
c['code'] = {'source_root': str(src), 'files': ['model.py', 'train.py'] + frozen}
c['primary_metric'] = {'name': 'accuracy', 'direction': 'higher', 'selection': 'best', 'target': 0.5, 'min_effect': 0.0}
c['guard_metrics'] = [{'name': 'brier', 'direction': 'lower', 'max_degradation': 0.5}]
c['baseline'] = {'source': 'demo MLP width 2', 'strength_rationale': 'demo only', 'tuning_parity': 'same epochs and lr'}
c['data'] = {'paths': [str(datadir)], 'labels_source': 'synthetic', 'split_reference': 'synth_data.py fixed seed',
             'group_unit': 'patient', 'evaluation_protocol': 'accuracy at 0.5'}
c['split_audit'] = {'command': ['{python}', 'audit_split.py', '--task', 'classification', '--output', '{output}'], 'timeout_seconds': 60}
c['test'] = {'policy': 'locked', 'reference': 'synth_data test split',
             'command': ['{python}', 'evaluate_test.py', '--task', 'classification', '--run-dir', '{run_dir}', '--output', '{output}'],
             'timeout_seconds': 60}
c['scope'] = {'editable_paths': ['model.py', 'train.py'], 'parameters': ['--task', '--width', '--epochs', '--learning-rate'], 'frozen_paths': frozen}
c['anomaly'] = {'max_drop': 0.9, 'unit': 'absolute', 'warmup_steps': 5, 'consecutive_outside_range': 1, 'reference_ranges': {}}
c['budget'] = {'total_seconds': 900, 'run_timeout_seconds': 120, 'max_candidates': 3, 'max_no_improvement': 3}
c['verification'] = {'seeds': [1, 2, 3], 'aggregation': 'mean', 'normal_range': [0, 1], 'max_std': 0.5,
                     'ci': {'method': 'paired_bootstrap', 'statistic': 'mean_per_case', 'resamples': 500, 'level': 0.95, 'seed': 7,
                            'lower_bound_rule': 'zero'}}
c['environment'] = {'python': PY, 'device': 'cpu', 'dependencies': {'numpy': numpy.__version__}, 'min_free_bytes': 1000000}
if MODE == 'matrix':
    c['matrix'] = {'reference': 'base', 'entries': [{'id': 'base', 'role': 'baseline', 'description': 'width 2'},
                                                    {'id': 'prop', 'role': 'proposed', 'description': 'width 16'}]}
cf = BASE / 'contract.json'; cf.write_text(json.dumps(c, indent=2), encoding='utf-8')
call('init', '--root', str(root), '--contract', str(cf))
call('approve', '--root', str(root), '--statement', 'e2e test approval')
call('audit', '--root', str(root))


def wait():
    for _ in range(600):
        s = call('status', '--root', str(root))
        if s['status'] not in ('running', 'testing'):
            return s
        time.sleep(1)


def cand(ident, phase, width, entry=None, epochs=40):
    cmd = BASE / f'{ident}.json'
    cmd.write_text(json.dumps(['{python}', 'train.py', '--task', 'classification', '--width', str(width), '--epochs', str(epochs), '--seed', '{seed}']))
    extra = ['--entry', entry] if entry else []
    rec = call('candidate', '--root', str(root), '--id', ident, '--phase', phase, '--command', str(cmd), '--description', 'width ' + str(width), *extra)
    rv = BASE / f'rv-{ident}.json'
    rv.write_text(json.dumps({'candidate_id': ident, 'commit': rec['commit'], 'reviewer': 'independent-subagent',
                              'agent_id': 'e2e-acceptance-runner-not-a-real-review', 'verdict': 'pass', 'findings': [],
                              'artifacts_read': ['train.py', 'model.py'], 'limitations': 'e2e acceptance-runner record'}))
    call('review', '--root', str(root), '--record', str(rv))


def runs(ident, seeds):
    st = None
    for s in seeds:
        call('run', '--root', str(root), '--candidate', ident, '--seed', str(s)); st = wait()
    return st


if MODE == 'search':
    cand('base', 'baseline', 2, epochs=1); st = runs('base', [1, 2, 3]); print('after baseline', st['status'], st['stage'])
    call('test', '--root', str(root), '--candidate', 'base', '--rationale', 'baseline reference for final comparison'); wait()
    cand('exp1', 'explore', 16); st = runs('exp1', [1]); print('after explore', st['status'], st['stage'])
    if st['status'] == 'verification_required':
        cand('ver1', 'verify', 16); st = runs('ver1', [1, 2, 3]); print('after verify', st['status'], st.get('pending_incident'))
        if st['status'] == 'awaiting_report':
            call('reported', '--root', str(root), '--statement', 'reported in e2e'); call('recover', '--root', str(root))
        if st['status'] == 'accepted':
            call('test', '--root', str(root), '--candidate', 'ver1', '--rationale', 'final accepted version'); wait()
else:
    cand('m-base', 'matrix', 2, 'base'); runs('m-base', [1, 2, 3])
    call('test', '--root', str(root), '--candidate', 'm-base', '--rationale', 'too early', ok=False)
    cand('m-prop', 'matrix', 16, 'prop'); st = runs('m-prop', [1, 2, 3]); print('after matrix', st['status'])
    call('test', '--root', str(root), '--candidate', 'm-base', '--rationale', 'reference'); wait()
    call('test', '--root', str(root), '--candidate', 'm-prop', '--rationale', 'proposed'); wait()
    call('test', '--root', str(root), '--candidate', 'm-prop', '--rationale', 'repeat', ok=False)
call('export', '--root', str(root))
print((root / 'report.md').read_text(encoding='utf-8'))
