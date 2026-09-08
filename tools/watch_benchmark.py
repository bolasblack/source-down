#!/usr/bin/env python3
"""Measure actual watch processes and retain the declared scope, raw samples and failures."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests-e2e"))
from support.case import Project, RunContext
from cases.watch.test_body_reads_linux import AccessTrace


PLUGIN = '''import json, os, sys
from pathlib import Path
initial=json.loads(sys.stdin.readline())
log=Path('.source-down/benchmark')
log.mkdir(parents=True, exist_ok=True)
with (log/'starts').open('a') as stream: stream.write(str(os.getpid())+'\\n')
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch=json.loads(line)
    with (log/'calls').open('a') as stream: stream.write(batch['batch_id']+'\\n')
    dependencies=[{'kind':'file','path':'plugin.py'}]
    text=Path('src/000.md').read_text()
    for number in range(5):
        if 'NEW_DEPENDENCY_'+str(number) in text:
            material='material/0000/'+str(10+number).zfill(4)+'.bin'
            value=Path(material).read_bytes()
            dependencies.append({'kind':'file','path':material})
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':[
        {'id':request['id'],'status':'ok','markdown':'Benchmark note','sources':[request['source']]} for request in batch['requests']],
        'append':[],
        'reports':{},'diagnostics':[],'dependencies':dependencies}), flush=True)
'''


def counters(process):
    root = Path('/proc') / str(process.scope.process.pid)
    fields = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    ticks = int(fields[11]) + int(fields[12])
    status = dict(line.split(':', 1) for line in (root / 'status').read_text().splitlines())
    io = dict(line.split(':', 1) for line in (root / 'io').read_text().splitlines())
    subscriptions = 0
    native_descriptors = []
    descriptors = list((root / 'fdinfo').iterdir())
    for descriptor in descriptors:
        try:
            count = sum(line.startswith('inotify ') for line in descriptor.read_text().splitlines())
            subscriptions += count
            if count: native_descriptors.append(descriptor.name)
        except FileNotFoundError:
            pass
    return {'cpu_seconds': ticks / os.sysconf('SC_CLK_TCK'),
            'process_read_char_bytes': int(io['rchar']),
            'rss_kib': int(status['VmRSS'].split()[0]),
            'peak_rss_kib': int(status['VmHWM'].split()[0]),
            'descriptors': len(descriptors), 'native_subscriptions': subscriptions,
            'native_descriptors': sorted(native_descriptors)}


def reads(events):
    result = Counter()
    for path, mask in events:
        role = 'ordinary_material' if path.startswith('material/') else 'selected_or_explicit'
        if mask & 0x20: result[role + '_opens'] += 1
        if mask & 0x01: result[role + '_access_events'] += 1
    return dict(result)


def quiet(process, trace, seconds):
    trace.take()
    before = counters(process)
    events = []
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        if process.scope.process.poll() is not None:
            raise AssertionError(process.stderr)
        events.extend(trace.take())
        time.sleep(0.02)  # Drain the independent kernel access trace during large Poll scans.
    events.extend(trace.take())
    after = counters(process)
    elapsed = time.monotonic() - started
    return {'seconds': elapsed, 'cpu_percent_one_core': 100 * (after['cpu_seconds'] - before['cpu_seconds']) / elapsed,
            'process_read_char_bytes': after['process_read_char_bytes'] - before['process_read_char_bytes'],
            'body_access': reads(events), 'after': after}


def batches(project):
    directory = project.root / '.source-down/benchmark'
    return {name: len((directory / name).read_text().splitlines()) if (directory / name).exists() else 0
            for name in ('starts', 'calls')}


def changed(project, process, edit, expected):
    count = process.stderr.count(b'pages; watching')
    before = batches(project)
    started = time.monotonic()
    edit()
    page = project.root / '.source-down/pages/src/000.md.md'
    process.wait_for(lambda: process.stderr.count(b'pages; watching') > count and expected in page.read_bytes(), timeout=40)
    return {'seconds': time.monotonic() - started,
            **{name: value - before[name] for name, value in batches(project).items()}}


def distribution(samples):
    values = sorted(sample['seconds'] for sample in samples)
    return {'p50_seconds': statistics.median(values), 'p95_seconds': values[-1],
            'p95_definition': 'nearest rank with five samples', 'samples': samples}


def notification_boundary(context, binary, project, configuration, trace, library, mode):
    arm = project.root / '.source-down/notify.arm'
    delivered = project.root / '.source-down/notify.delivered'
    arm.unlink(missing_ok=True)
    delivered.unlink(missing_ok=True)
    project.write_text('source-down.toml', configuration)
    environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_NOTIFY_ROOT=str(project.root),
                       SD_WATCH_NOTIFY_MODE=mode, SD_WATCH_NOTIFY_ARM=str(arm))
    with context.running([binary, 'watch', 'src', '--root', project.root], cwd=project.root, env=environment) as process:
        process.wait_for(lambda: b'pages; watching' in process.stderr, timeout=40)
        assert b'backend native' in process.stderr and b'switching to poll' not in process.stderr
        trace.take()
        before, calls = counters(process), batches(project)
        started = time.monotonic()
        arm.write_text('deliver the controlled notification at the reader boundary')
        project.write_text('notification-wakeup', 'wake native reader\n')
        def handled():
            current = counters(process)
            if not delivered.exists(): return False
            if mode == 'rescan':
                return current['native_subscriptions'] == before['native_subscriptions'] and current['native_descriptors'] != before['native_descriptors']
            return current['native_subscriptions'] == 0 and b'switching to poll' in process.stderr
        process.wait_for(handled, timeout=40)
        after = counters(process)
        result = {'seconds_until_coverage_transition': time.monotonic() - started,
                  'cpu_seconds': after['cpu_seconds'] - before['cpu_seconds'],
                  'before': before, 'after': after, 'body_access': reads(trace.take()),
                  'plugin_activity': {name: value - calls[name] for name, value in batches(project).items()}}
        assert not result['body_access'].get('ordinary_material_opens'), result
        assert not any(result['plugin_activity'].values()), result
        if mode == 'error':
            result['poll_healthy_idle'] = quiet(process, trace, 1.3)
            project.write_text('source-down.toml', 'invalid = [\n')
            process.wait_for(lambda: (trace.take(), b'configuration failure; watching' in process.stderr)[1])
            result['poll_fault_idle'] = quiet(process, trace, 1.3)
        process.interrupt()
        assert process.wait().returncode == 130
    return result


def measure(binary, output):
    output = output / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    declaration = json.loads((ROOT / 'docs/engineering/watch-baseline.json').read_text())
    report = {'platform': platform.platform(), 'machine': platform.machine(), 'logical_cpus': os.cpu_count(),
              'binary': str(binary), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'declaration': declaration, 'cases': [], 'status': 'running', 'evidence_directory': str(output),
              'counter_scope': 'Linux CLI process and its threads; plugin initialization/batch counts recorded separately',
              'access_scope': 'independent kernel IN_OPEN/IN_ACCESS watches on every fixture body, adding each discovered material before use; events may coalesce',
              'rchar_scope': 'all CLI read() bytes, including native notification delivery; not a file-body byte counter',
              'controlled_event_scope': 'actual notify reader with a supplied IN_Q_OVERFLOW record or EIO; transition time ends after old native handles retire; not natural kernel overflow',
              'digest_evidence': 'zero native idle body opens/reads cross-checked with the production sampling-interface component tests'}
    output.mkdir(parents=True, exist_ok=True)
    context = RunContext(ROOT, output, binary, binary.parent / 'examples/spec-plugin')
    limits = declaration['limits']
    try:
        library = output / 'notification-boundary.so'
        compiled = context.command([sys.executable, ROOT / 'tools/build.py', '--', ROOT / 'tools/cc', '-shared', '-fPIC',
                                    ROOT / 'tests-e2e/fixtures/watch/notification_publication.c', '-o', library, '-ldl'], cwd=ROOT, timeout=60)
        assert compiled.returncode == 0, compiled.stderr
        for size in declaration['sizes']:
            for mode in ('none', 'include', 'external'):
                with tempfile.TemporaryDirectory(prefix='source-down-watch-benchmark-') as temporary:
                    project = Project(context, temporary)
                    body_bytes = (size['material_bytes'] + size['files'] - 1) // size['files']
                    for number in range(size['files']):
                        if number < 10:
                            name = f'src/{number:03}.md'
                            content = (f'Paragraph {number}.\n' * body_bytes).encode()[:body_bytes - 1] + b'\n'
                            if mode == 'include': content += b'{% include "shared.md" %}\n\n' * 50
                            elif mode == 'external': content += b'{% note %}\n\n' * 50
                        else:
                            name = f'material/{number // 100:04}/{number:04}.bin'
                            content = (bytes(range(256)) * ((body_bytes + 255) // 256))[:body_bytes]
                        project.write_bytes(name, content)
                    project.write_text('shared.md', '# Shared\n\nRepeated material.\n')
                    configuration = 'config_version=1\n'
                    if mode == 'external':
                        project.write_text('plugin.py', PLUGIN)
                        configuration += '[plugins.measure]\ncommand=["python","plugin.py"]\ndirectives=["note"]\n'
                    project.write_text('source-down.toml', configuration)
                    paths = {str(p.relative_to(project.root)): p for p in project.root.rglob('*') if p.is_file()}
                    case = {'files': size['files'], 'mode': mode,
                            'selected_files': 10, 'selected_bytes': sum(p.stat().st_size for n, p in paths.items() if n.startswith('src/')),
                            'ordinary_material_files': size['files'] - 10,
                            'ordinary_material_bytes': sum(p.stat().st_size for n, p in paths.items() if n.startswith('material/')),
                            'actual_fixture_bytes': sum(p.stat().st_size for p in paths.values())}
                    report['cases'].append(case)
                    assert case['actual_fixture_bytes'] >= size['material_bytes'], case
                    with AccessTrace(paths) as trace:
                        started = time.monotonic()
                        with context.running([binary, 'watch', 'src', '--root', project.root], cwd=project.root) as process:
                            process.wait_for(lambda: b'watch round 1: starting' in process.stderr, timeout=40)
                            case['subscription_and_baseline_seconds'] = time.monotonic() - started
                            process.wait_for(lambda: b'pages; watching' in process.stderr, timeout=40)
                            case['initial'] = {'seconds': time.monotonic() - started, **counters(process), **batches(project), 'body_access': reads(trace.take())}
                            assert b'watch: backend native' in process.stderr and b'switching to poll' not in process.stderr, process.stderr
                            assert not case['initial']['body_access'].get('ordinary_material_opens'), case
                            case['native_healthy_idle'] = quiet(process, trace, 1.3)
                            original = project.read_bytes('src/000.md')
                            samples = []
                            for number in range(5):
                                marker = f'Known edit {number}'.encode()
                                trace.take()
                                sample = changed(project, process, lambda: project.write_bytes('src/000.md', original + b'\n' + marker + b'\n'), marker)
                                sample['body_access'] = reads(trace.take())
                                assert not sample['body_access'].get('ordinary_material_opens'), sample
                                assert sample['starts'] == 0, sample
                                samples.append(sample)
                            case['known_change'] = distribution(samples)
                            samples = []
                            for number in range(5):
                                marker = f'NEW_DEPENDENCY_{number}'.encode() if mode == 'external' else f'Discovered material {number}'.encode()
                                project.write_bytes(f'discovered-{number}.md', marker + b'\n')
                                trace.add({f'discovered-{number}.md': project.root / f'discovered-{number}.md'})
                                addition = b'\n' + marker + b'\n' if mode == 'external' else f'\n{{% include "discovered-{number}.md" %}}\n'.encode()
                                samples.append(changed(project, process, lambda: project.write_bytes('src/000.md', original + addition), marker))
                            case['new_dependency'] = distribution(samples)
                            samples = []
                            for number in range(5):
                                samples.append(changed(project, process,
                                    lambda: project.write_text('source-down.toml', configuration + f'\n# Configuration revision {number}\n'), marker))
                            case['configuration_restart'] = distribution(samples)
                            def burst():
                                for number in range(4500):
                                    project.write_text(f'material/burst/{number}.txt', 'ordinary event\n')
                                trace.add({str(p.relative_to(project.root)): p for p in (project.root / 'material/burst').iterdir()})
                                project.write_text('src/created/new.md', 'New directory input\n')
                                project.write_bytes('src/000.md', original + b'\nEvent burst proof\n')
                            case['event_burst_and_directory_creation'] = changed(project, process, burst, b'Event burst proof')
                            case['event_burst_and_directory_creation']['after'] = counters(process)
                            def replace_directory():
                                retired = project.root / '.source-down/retired-src'
                                (project.root / 'src').rename(retired)
                                shutil.copytree(retired, project.root / 'src')
                                project.write_bytes('src/000.md', original + b'\nDirectory replacement proof\n')
                            case['directory_replacement'] = changed(project, process, replace_directory, b'Directory replacement proof')
                            case['post_replacement_edit'] = changed(project, process,
                                lambda: project.write_bytes('src/000.md', original + b'\nReplacement subscription proof\n'), b'Replacement subscription proof')
                            trace.add({str(p.relative_to(project.root)): p for p in (project.root / 'src').rglob('*') if p.is_file()})
                            failures = process.stderr.count(b'configuration failure; watching')
                            project.write_text('source-down.toml', 'invalid = [\n')
                            process.wait_for(lambda: process.stderr.count(b'configuration failure; watching') > failures)
                            case['native_fault_idle'] = quiet(process, trace, 1.3)
                            process.interrupt()
                            assert process.wait().returncode == 130
                        for event_mode in ('rescan', 'error'):
                            case['controlled_' + event_mode] = notification_boundary(context, binary, project, configuration, trace, library, event_mode)
                        project.write_text('source-down.toml', configuration)
                        trace.take()
                        with context.running([binary, 'watch', 'src', '--poll', '--root', project.root], cwd=project.root) as process:
                            process.wait_for(lambda: (trace.take(), b'pages; watching' in process.stderr)[1], timeout=40)
                            assert b'watch: backend poll' in process.stderr, process.stderr
                            trace.take()
                            case['poll_healthy_idle'] = quiet(process, trace, 1.3)
                            project.write_text('source-down.toml', 'invalid = [\n')
                            process.wait_for(lambda: (trace.take(), b'configuration failure; watching' in process.stderr)[1])
                            case['poll_fault_idle'] = quiet(process, trace, 1.3)
                            process.interrupt()
                            assert process.wait().returncode == 130
                    for name in ('native_healthy_idle', 'native_fault_idle'):
                        assert not case[name]['body_access'], (name, case[name])
                        assert case[name]['cpu_percent_one_core'] <= limits['native_quiet_cpu_percent_one_core'], case[name]
                    assert case['subscription_and_baseline_seconds'] <= limits[f"subscription_seconds_{size['files']}"], case
                    assert case['initial']['seconds'] <= limits[f"first_publication_seconds_{size['files']}"], case
                    assert case['initial']['peak_rss_kib'] <= limits['max_rss_mib'] * 1024, case
                    assert case['known_change']['p95_seconds'] <= limits['known_change_p95_seconds'], case
                    assert case['configuration_restart']['p95_seconds'] <= limits['unknown_dependency_or_restart_p95_seconds'], case
                    assert case['new_dependency']['p95_seconds'] <= limits['unknown_dependency_or_restart_p95_seconds'], case
                    print(f"watch benchmark: {size['files']} {mode} passed", flush=True)
                    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        report['status'] = 'passed'
    except BaseException as error:
        report['status'], report['error'] = 'failed', str(error)
        raise
    finally:
        report['commands'] = context.commands
        (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        context.resources.close()
    return report


if __name__ == '__main__':
    measure((ROOT / 'target/release/source-down').resolve(), ROOT / '.source-down/watch-benchmark')
