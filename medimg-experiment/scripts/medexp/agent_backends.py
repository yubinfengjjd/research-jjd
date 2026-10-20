"""Native CLI protocol selection, restricted argv and auditable event identity."""
import copy
import json
import os
from pathlib import Path
import re
import uuid

from .common import GateError, require, read_json, safe_path

READ_ONLY_TOOLS='restricted CLI tools: Read,Glob,Grep; not an OS sandbox'
CONNECTION_ENV=frozenset({
    'ANTHROPIC_AUTH_TOKEN','ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL','ANTHROPIC_MODEL',
    'CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_SMALL_FAST_MODEL','ANTHROPIC_CUSTOM_HEADERS',
})
CLAUDE_METADATA_PATTERN=r'^adaptive/agents/[A-Za-z0-9_-]+/(input|invocation)\.json$'


def provider_schema(backend, base_schema):
    """Constrain Claude metadata to files in its restricted invocation scope."""
    if backend!='claude':return base_schema
    schema=copy.deepcopy(base_schema)
    if 'additional_evidence' in schema.get('properties',{}):
        metadata=copy.deepcopy(schema['properties']['additional_evidence'])
        metadata['items']['pattern']=CLAUDE_METADATA_PATTERN
        schema['properties']['additional_evidence']=metadata
    return schema


def selected_backend(delegation):
    backend=delegation.get('agent_backend','codex')
    require(backend in ('codex','claude'),'agent_backend必须为codex或claude')
    return backend


def validate_backend(delegation):
    backend=selected_backend(delegation);config=delegation.get(backend,{})
    require(isinstance(config,dict),'后端配置必须为对象')
    exe=config.get('executable')
    require(isinstance(exe,str) and Path(exe).is_absolute() and safe_path(exe).is_file(),
            '必须提供真实本地 '+backend+' 可执行文件绝对路径')
    if backend=='claude':
        require(Path(exe).suffix.lower()=='.exe','Claude必须使用原生exe，禁止shell包装器')
        turns=config.get('max_turns')
        require(isinstance(turns,int) and not isinstance(turns,bool) and 1<=turns<=100,
                'claude.max_turns必须为1..100整数')
    return backend


def child_environment(delegation, parent=None, settings_path=None):
    """Load only existing user connection env in memory; never hooks or plugins."""
    env=dict(os.environ if parent is None else parent);env['PYTHONUTF8']='1'
    if selected_backend(delegation)!='claude':return env
    path=Path(settings_path) if settings_path is not None else (
        Path(env['CLAUDE_CONFIG_DIR']) if env.get('CLAUDE_CONFIG_DIR') else Path.home()/'.claude')/'settings.json'
    path=safe_path(path)
    try:
        settings=json.loads(path.read_text(encoding='utf-8-sig'))
    except FileNotFoundError:return env
    except (OSError,ValueError):raise GateError('Claude用户连接配置无法读取或不是有效JSON') from None
    require(isinstance(settings,dict),'Claude用户配置必须为对象')
    values=settings.get('env',{})
    require(isinstance(values,dict) and all(isinstance(k,str) and isinstance(v,str) and '\0' not in k+v for k,v in values.items()),
            'Claude用户配置env必须为有效字符串映射')
    env.update({k:v for k,v in values.items() if k in CONNECTION_ENV})
    return env


def build_argv(root, delegation, directory, prompt, schema, session=None):
    backend=validate_backend(delegation);exe=delegation[backend]['executable']
    schema=provider_schema(backend,schema)
    if backend=='codex':
        return [exe,'exec','--ephemeral','--json','--color','never','-s','read-only','-C',str(root/'worktree'),
                '--output-schema',str(directory/'schema.json'),'-o',str(directory/'result.json'),prompt]
    require(isinstance(session,str) and str(uuid.UUID(session))==session,'Claude需要新的UUID会话身份')
    return [exe,'-p',prompt,'--bare','--restricted','--tools','Read,Glob,Grep',
            '--disallowedTools','mcp__*','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
            '--no-session-persistence','--session-id',session,'--permission-mode','plan',
            '--add-dir',str(directory),'--output-format','stream-json','--verbose',
            '--json-schema',json.dumps(schema,ensure_ascii=False,separators=(',',':')),
            '--max-turns',str(delegation['claude']['max_turns'])]


def recorded_argv(argv, backend):
    recorded=list(argv);recorded[2 if backend=='claude' else -1]='<saved prompt.txt>'
    return recorded


def read_events(path, strict=True):
    events=[]
    for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
        try:event=json.loads(line)
        except json.JSONDecodeError:
            # Native stderr diagnostics may share the log; malformed JSON events fail closed.
            require(not strict or not line.lstrip().startswith('{'),'CLI事件JSON损坏')
            continue
        require(isinstance(event,dict),'CLI事件必须为对象');events.append(event)
    return events


def validate_output(value, schema):
    """Validate the deliberately small strict structured-result schema recursively."""
    kind=schema['type']
    if kind=='object':
        require(isinstance(value,dict) and set(value)==set(schema['properties']),'结构化结果字段不匹配')
        for key,subschema in schema['properties'].items():validate_output(value[key],subschema)
    elif kind=='array':
        require(isinstance(value,list),'结构化结果列表类型不匹配')
        for item in value:validate_output(item,schema['items'])
    elif kind=='string':
        require(isinstance(value,str),'结构化结果字符串类型不匹配')
        if 'pattern' in schema:require(re.fullmatch(schema['pattern'],value) is not None,'结构化结果字符串格式不匹配')
    elif kind=='boolean':require(isinstance(value,bool),'结构化结果布尔类型不匹配')
    else:raise GateError('不支持的结构化结果schema类型')
    if 'enum' in schema:require(value in schema['enum'],'结构化结果枚举无效')
    return value


def parse_claude_events(events, session, schema, expected_cwd):
    schema=provider_schema('claude',schema)
    require(isinstance(events,list) and all(isinstance(e,dict) for e in events),'Claude事件必须为对象列表')
    require(isinstance(session,str) and str(uuid.UUID(session))==session,'Claude会话必须为UUID')
    require(all(not e.get('session_id') or e['session_id']==session for e in events),'Claude事件会话身份不匹配')
    init=[i for i,e in enumerate(events) if e.get('type')=='system' and e.get('subtype')=='init']
    terminal=[i for i,e in enumerate(events) if e.get('type')=='result']
    require(len(init)==1 and len(terminal)==1 and init[0]<terminal[0],'Claude必须有单一新会话init和单一终结result')
    start=events[init[0]];result=events[terminal[0]]
    require(start.get('session_id')==session and result.get('session_id')==session,'Claude缺少真实匹配会话身份')
    cwd=start.get('cwd');expected=safe_path(expected_cwd)
    require(isinstance(cwd,str) and Path(cwd).is_absolute() and safe_path(cwd)==expected and expected.is_dir(),
            'Claude实际init工作目录与受管源码目录不匹配')
    tools=start.get('tools')
    require(isinstance(tools,list) and all(isinstance(name,str) and name in ('Read','Glob','Grep','StructuredOutput') for name in tools),
            'Claude实际会话暴露了未经授权的工具或缺少工具清单')
    require(result.get('subtype')=='success' and result.get('is_error') is False,'Claude终结结果未成功')
    require('structured_output' in result,'Claude没有结构化最终输出')
    return validate_output(result['structured_output'],schema)


def verify_replay(root, delegation, folder, record, schema):
    """Bind selected provider, actual restricted command and saved terminal events."""
    backend=validate_backend(delegation)
    require(record.get('backend','codex')==backend,'审查后端与授权后端不一致')
    thread=record.get('thread_id');require(isinstance(thread,str) and thread.strip(),'缺少真实会话身份')
    try:uuid.UUID(thread)
    except ValueError:raise GateError('审查会话身份不是UUID') from None
    argv=record.get('argv',[])
    require(isinstance(argv,list) and argv and all(isinstance(v,str) for v in argv),'审查argv无效')
    require(os.path.normcase(str(safe_path(argv[0])))==os.path.normcase(str(safe_path(delegation[backend]['executable']))),
            '实际CLI可执行文件身份不匹配')
    events=read_events(folder/'events.jsonl',strict=backend=='claude');raw=read_json(folder/'result.json')
    if backend=='claude':
        cwd=safe_path(root/'worktree')
        require(record.get('cwd')==str(cwd),'Claude审计工作目录与受管源码目录不匹配')
        expected=build_argv(root,delegation,folder,'<saved prompt.txt>',schema,thread)
        require(argv==expected and record.get('requested_session_id')==thread,'实际Claude限制参数/会话不匹配')
        require(record.get('sandbox') is None and record.get('read_only_mechanism')==READ_ONLY_TOOLS,
                '实际Claude只读机制不匹配')
        require(parse_claude_events(events,thread,schema,cwd)==raw,'Claude实际终结输出与已保存结果不匹配')
        init=next(e for e in events if e.get('type')=='system' and e.get('subtype')=='init')
        require(record.get('model')==init.get('model') and record.get('actual_tools')==init.get('tools'),
                'Claude实际模型/工具事件与审计记录不匹配')
    else:
        require(record.get('sandbox')=='read-only','实际Codex沙箱不匹配')
        if 'backend' in record:
            require(argv==build_argv(root,delegation,folder,'<saved prompt.txt>',schema),'实际Codex限制参数不匹配')
        else:
            require('exec' in argv and '--ephemeral' in argv and '--json' in argv,'实际Codex命令身份不匹配')
            require('-s' in argv and argv[argv.index('-s')+1]=='read-only' and '-C' in argv and
                    safe_path(argv[argv.index('-C')+1])==root/'worktree','实际调用沙箱/工作目录不匹配')
        require(any(e.get('type')=='thread.started' and e.get('thread_id')==thread for e in events)
                and any(e.get('type')=='turn.completed' for e in events),'没有匹配的真实新会话/完成事件')
    return raw
