"""Author limits and lexical diagnostics must not force filler prose."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import manuscript_check as mc


def test_repeated_source_reports_context_without_uniqueness_pressure(tmp_path):
    path = tmp_path / 'Discussion_EN.md'
    path.write_text('Prior work motivates the cohort choice (PMID: 12345678).\n\n'
                    'Its measurement protocol also defines our endpoint (PMID: 12345678).', encoding='utf-8')
    findings = mc.check('discussion', path)
    repeated = [f for f in findings if f['rule'] == 'pmid-repeat']
    assert repeated and repeated[0]['level'] == 'INFO'
    assert '一般只' not in repeated[0]['msg']
    assert 'cohort choice' in repeated[0]['context'] and 'measurement protocol' in repeated[0]['context']


def test_no_citation_volume_target_is_manufactured(tmp_path):
    from citation_stats import load_targets, collect
    targets, warnings = load_targets(tmp_path)
    assert all(v is None for v in targets['values'].values())
    assert not [f for f in collect(tmp_path)['warnings'] if f['rule'] == 'citation-quota']


def test_style_means_and_generic_counts_are_diagnostic_only():
    from style_check import analyze_style
    text = ' '.join(['word'] * 61) + '; a related clause; one final clause.'
    result = analyze_style(text)
    assert result['findings'] and all(f['level'] == 'WARN' for f in result['findings'])
    assert '短句用连词' not in ' '.join(f['hint'] for f in result['findings'])


def test_profile_style_severity_matches_emission():
    diagnostic_rules = {'sentence-opener', 'negative-gap', 'scope-disclaimer', 'agrees-with',
                        'extends', 'consistent-with', 'contrasts-with', 'would-test',
                        'negative-boundary', 'we-found-opener'}
    for profile in mc.PROFILES.values():
        assert all(level == mc.W for level, rule, *_ in profile['rules'] if rule in diagnostic_rules)


def test_explicit_author_style_limits_can_block():
    from style_check import analyze_style
    result = analyze_style('One clause; another clause.', required_limits={'prose_semicolons_max':0})
    assert any(f['level']=='ERROR' and f['rule']=='semicolon-chain' for f in result['findings'])
    with pytest.raises(ValueError):analyze_style('Clear prose.',required_limits={'sentence_max_words':True})


def test_generic_lexical_and_intro_length_heuristics_do_not_block(tmp_path):
    path=tmp_path/'Introduction_EN.md'
    path.write_text(('word '*1201)+'\n\nTo our knowledge, this does not prove clinical benefit. '
                    'To our knowledge, a novel cohort remains relevant.',encoding='utf-8')
    findings=mc.check('introduction',path)
    for rule in ('word-count','to-our-knowledge','hype'):
        assert any(f['rule']==rule and f['level']==mc.W for f in findings)
    assert not [f for f in findings if f['level']==mc.E]
    path.write_text('This does not prove that the treatment works.',encoding='utf-8')
    assert not [f for f in mc.check('discussion',path) if f['rule']=='overclaim' and f['level']==mc.E]


@pytest.mark.parametrize('section', ['methods', 'results', 'discussion'])
def test_short_evidence_complete_section_has_no_generic_minimum(tmp_path, section):
    path = tmp_path / 'Manuscript_EN.md'
    path.write_text('The prespecified estimate was lower in the held-out cohort.', encoding='utf-8')
    assert not [f for f in mc.check(section, path) if f['rule'] == 'word-count']


def test_project_limit_is_enforced_without_confusing_citation_quota(tmp_path):
    (tmp_path / 'PROJECT.md').write_text('## 写作目标\n- Results：≥25\n', encoding='utf-8')
    (tmp_path / 'writing-limits.json').write_text(json.dumps({'results': {'max': 8}}), encoding='utf-8')
    folder = tmp_path / '04_manuscript' / 'Results'
    folder.mkdir(parents=True)
    path = folder / 'Results_EN.md'
    path.write_text('The prespecified estimate was lower in the held-out cohort.', encoding='utf-8')
    findings = mc.check('results', path)
    assert any(f['rule'] == 'word-count' and f['level'] == mc.E for f in findings)


def test_lexical_repetition_is_a_signal_and_not_an_error(tmp_path):
    path = tmp_path / 'Discussion_EN.md'
    path.write_text('This agrees with prior work. That agrees with the estimate. '
                    'The result agrees with this explanation.', encoding='utf-8')
    findings = mc.check('discussion', path)
    assert any(f['rule'] == 'agrees-with' and f['level'] == mc.W for f in findings)
    assert not [f for f in findings if f['rule'] == 'agrees-with' and f['level'] == mc.E]


def test_malformed_declared_limits_fail_explicitly_in_cli(tmp_path):
    (tmp_path / 'PROJECT.md').write_text('# Project', encoding='utf-8')
    (tmp_path / 'writing-limits.json').write_text('{"results":{"max":true}}', encoding='utf-8')
    path = tmp_path / 'Results_EN.md'
    path.write_text('A measured finding.', encoding='utf-8')
    result = subprocess.run([sys.executable, '-X', 'utf8', str(Path(mc.__file__)),
                             'results', str(path), '--json'], capture_output=True,
                            text=True, encoding='utf-8')
    assert result.returncode == 1
    findings = json.loads(result.stdout)
    assert any(f['rule'] == 'word-limits-config' and f['level'] == mc.E for f in findings)


def test_explicit_caption_minimum_is_per_caption(tmp_path):
    (tmp_path / 'PROJECT.md').write_text('# Project', encoding='utf-8')
    (tmp_path / 'writing-limits.json').write_text('{"legends":{"min":10}}', encoding='utf-8')
    path = tmp_path / 'Figure_Legends_EN.md'
    path.write_text('**Figure 1. Measurement.** A measured value.', encoding='utf-8')
    findings = mc.check('legends', path)
    assert any(f['rule'] == 'legend-length' and f['level'] == mc.E for f in findings)


def test_meta_jargon_and_generic_validation_closer_warn_only(tmp_path):
    abs_path = tmp_path / 'Abstract_EN.md'
    abs_path.write_text(
        '## Abstract\n\n### Background\nRetinal OCT assessment.\n\n### Methods\nWe evaluated 100 scans.\n\n'
        '### Results\nAccuracy was 0.91.\n\n### Conclusions\nThis model served as a structured method, requiring validation.\n',
        encoding='utf-8',
    )
    findings = mc.check('abstract', abs_path)
    rules = {f['rule']: f['level'] for f in findings}
    assert rules.get('meta-jargon') == mc.W
    assert rules.get('generic-validation-closer') == mc.W

    res_path = tmp_path / 'Results_EN.md'
    res_path.write_text(
        '## Results\n\nFive descriptive analyses were descriptive, descriptive, descriptive, and descriptive.',
        encoding='utf-8',
    )
    res_rules = {f['rule']: f['level'] for f in mc.check('results', res_path)}
    assert 'descriptive-repeat' not in res_rules

    whereas_path = tmp_path / 'Whereas_EN.md'
    whereas_path.write_text(
        '# Results\n\nWhereas cohort A improved, cohort B declined. '
        'Whereas cohort C improved, cohort D declined. '
        'Whereas cohort E improved, cohort F declined.\n',
        encoding='utf-8',
    )
    whereas_rules = {f['rule']: f['level'] for f in mc.check('results', whereas_path)}
    assert 'rather-than' not in whereas_rules
    assert 'descriptive-repeat' not in whereas_rules


def test_cycle2_heading_density_citation_zh_and_abstract_warnings(tmp_path):
    res_path = tmp_path / 'Results_EN.md'
    res_zh = tmp_path / 'Results_ZH.md'
    res_path.write_text(
        '# Results\n\n'
        '## 3.4 Transfer holds in most external cohorts\n\n'
        'Sentence one (Fig. 6A). Sentence two (Fig. 6A). Sentence three (Fig. 6A). '
        'Sentence four. Sentence five. Sentence six. Sentence seven. Sentence eight. Sentence nine.\n\n'
        'Paragraph A complete prediction-set data supplied as supplementary data. '
        'Paragraph B complete prediction-set data supplied as supplementary data. '
        'Paragraph C complete prediction-set data supplied as supplementary data.\n',
        encoding='utf-8',
    )
    res_zh.write_text(
        '# 结果\n\n## 3.4 迁移在多数外部队列保持\n\n在 seed 0 下如 Fig. 6A 所示。 下一句。\n',
        encoding='utf-8',
    )
    findings = mc.check('results', res_path, zh_path=res_zh)
    rules = {f['rule']: f['level'] for f in findings}
    for r in ('heading-defensive-vague', 'citation-repeat', 'paragraph-dense', 'boilerplate-repeat',
              'zh-unlocalized-seed', 'zh-unlocalized-figtable', 'zh-space-after-period'):
        assert rules.get(r) == mc.W, (r, findings)

    disc_path = tmp_path / 'Discussion_EN.md'
    disc_path.write_text(
        '# Discussion\n\nThis remained unresolved. Another did not establish causality. '
        'It remained unresolved and another remains descriptive.\n',
        encoding='utf-8',
    )
    disc_rules = {f['rule']: f['level'] for f in mc.check('discussion', disc_path)}
    assert disc_rules.get('defensive-hedging-cluster') == mc.W

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'medical-sci-abstract' / 'scripts'))
    import check_abstract as ca
    abs_text = (
        '## Abstract\n\n### Background\nOne two.\n\n### Methods\nThree four.\n\n'
        '### Results\nFirst clause; second clause. Third; fourth. Fifth; sixth. S4. S5. S6. S7.\n\n'
        '### Conclusions\nFive six.\n'
    )
    res = ca.analyze(abs_text, limit=len('One two. Three four. First clause; second clause. Third; fourth. Fifth; sixth. S4. S5. S6. S7. Five six.'.split()))
    assert res['errors'] == []
    joined = '\n'.join(res['warnings'])
    assert 'word-limit-margin' in joined
    assert 'results-sentences' in joined
    assert 'results-semicolons' in joined

    res2 = tmp_path / 'Results2_EN.md'
    res2_zh = tmp_path / 'Results2_ZH.md'
    res2.write_text(
        '# Results\n\nFirst result (Supplementary Fig. S6). Second result (Supplementary Fig. S6).\n\n'
        'Third result (Supplementary Fig. S8; Supplementary Fig. S8C, D).\n',
        encoding='utf-8',
    )
    res2_zh.write_text(
        '# 结果\n\n**图 1. 标题**(a) 三个 种子 平均为 0.4% 。****表注：**external oracle 对应 True 与 energy。\n',
        encoding='utf-8',
    )
    rules2 = {f['rule']: f['level'] for f in mc.check('results', res2, zh_path=res2_zh)}
    for r in ('citation-adjacent-repeat', 'citation-redundant-parent', 'zh-seed-space',
              'zh-space-before-punct', 'zh-bold-artifact', 'zh-unlocalized-english'):
        assert rules2.get(r) == mc.W, (r, rules2)

    res3 = tmp_path / 'Results3_EN.md'
    res3_zh = tmp_path / 'Results3_ZH.md'
    res3.write_text(
        '# Results\n\nA (Supplementary Fig. S10A). B (Supplementary Fig. S10B). '
        'C (Supplementary Fig. S10B). D (Supplementary Fig. S10).\n\n'
        'E (prediction-set supplementary data). F (prediction-set supplementary data). '
        'G (complete prediction-set data supplied as supplementary data).\n',
        encoding='utf-8',
    )
    res3_zh.write_text(
        '# 结果\n\n**图 1. 概述。** (a) 首句引用已有研究（PMID: 12345678）。'
        '（b）下一句（1−alpha）与 0.5 px 及 3.87 µm/px。\n\n'
        '**附表 S4。** (d) 种子间一致率与种子0说明及 \\(\\alpha = 0.10\\) 参数。\n',
        encoding='utf-8',
    )
    rules3 = {f['rule']: f['level'] for f in mc.check('results', res3, zh_path=res3_zh)}
    assert rules3.get('citation-repeat') == mc.W
    assert rules3.get('boilerplate-repeat') == mc.W
    assert rules3.get('zh-unlocalized-english') == mc.W
    assert 'zh-space-before-punct' not in rules3
    assert 'zh-space-after-period' not in rules3
    assert 'zh-seed-space' not in rules3


def test_cycle9_cjk_space_num_boundary_unlocalized_terms_and_abstract_semicolon(tmp_path):
    """Cycle-9 checker regression: CJK spaces, compact seed numbers, logit/bootstrap, closer, 1-semicolon."""
    meth_en = tmp_path / 'Methods_EN.md'
    meth_zh = tmp_path / 'Methods_ZH.md'
    meth_en.write_text('# Methods\n\nModel initialization used seed 20261008 and bootstrap resampling.', encoding='utf-8')
    meth_zh.write_text(
        '# 方法\n\n## 并列 标题不报错\n\n| 列出 表内 | 按类别 |\n| --- | --- |\n'
        '模型训练采用种子20261008。此处列出 按类别统计并对logit采用bootstrap重采样。\n',
        encoding='utf-8',
    )
    meth_rules = {f['rule']: f['level'] for f in mc.check('methods', meth_en, zh_path=meth_zh)}
    assert 'zh-number' not in meth_rules
    assert meth_rules.get('zh-cjk-space') == mc.W
    assert meth_rules.get('zh-unlocalized-english') == mc.W

    abs_en = tmp_path / 'Abstract_EN.md'
    abs_en.write_text(
        '## Abstract\n\n### Background\nRetinal OCT assessment.\n\n### Methods\nWe evaluated 100 scans.\n\n'
        '### Results\nAUROC was 0.90; Edema AP was 0.45.\n\n'
        '### Conclusions\nSafe deployment requires prospective external testing across devices.\n',
        encoding='utf-8',
    )
    abs_rules = {f['rule']: f['level'] for f in mc.check('abstract', abs_en)}
    assert abs_rules.get('generic-validation-closer') == mc.W

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'medical-sci-abstract' / 'scripts'))
    import check_abstract as ca
    res = ca.analyze(abs_en.read_text(encoding='utf-8'))
    assert any('results-semicolons' in w for w in res['warnings'])

    clean_abs = abs_en.read_text(encoding='utf-8').replace('AUROC was 0.90; Edema AP was 0.45.', 'AUROC was 0.90. Edema AP was 0.45.')
    res_clean = ca.analyze(clean_abs)
    assert not any('results-semicolons' in w for w in res_clean['warnings'])

    math_zh = tmp_path / 'Math_ZH.md'
    math_en = tmp_path / 'Math_EN.md'
    math_en.write_text('# Methods\n\nLearning rates were 1e-4 and 1e-5.', encoding='utf-8')
    math_zh.write_text('# 方法\n\n前端与骨干学习率分别为 \\(10^{-4}\\) 和 \\(10^{-5}\\)。权重衰减为 0.05。\n', encoding='utf-8')
    math_rules = {f['rule']: f['level'] for f in mc.check('methods', math_en, zh_path=math_zh)}
    assert 'zh-cjk-space' not in math_rules
