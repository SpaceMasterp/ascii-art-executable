"""Real-A eligibility and extraction boundary regression tests."""
from codeart.prepass import inspect_file, selected_source


def test_real_dependencies_and_original_lines():
    text = '#include <stdio.h>\nint g=1;\nint bad(void){return g;}\nint good(int x){return x+1;}\nint main(void){return 0;}\n'
    result = inspect_file(text)
    assert [(c.name, c.a_status) for c in result.candidates] == [('bad', 'FAIL'), ('good', 'PASS'), ('main', 'FAIL')]
    assert result.candidates[0].diagnostic['line'] == 3
    assert result.selected == 'good'
    assert selected_source(result) == 'int good(int x){return x+1;}'
    assert result.ignored_lines == [dict(start_line=1, end_line=3, reason='Outside the selected function'), dict(start_line=5, end_line=5, reason='Outside the selected function')]


def test_literals_comments_prototypes_and_selection():
    text = 'int proto(int x);\n/* } 中文 */\nint first(int x){ /* { */ return x;}\nint second(void){return 2;}'
    result = inspect_file(text, 'second')
    assert [c.name for c in result.candidates] == ['first', 'second']
    assert result.selected == 'second'
    assert inspect_file(text, 'missing').error == 'NO_ELIGIBLE_FUNCTION'


def test_conditional_definitions_are_not_silently_enabled():
    result = inspect_file('#if 0\nint disabled(void){return 1;}\n#endif\n')
    assert result.error == 'NO_ELIGIBLE_FUNCTION'
    assert result.candidates[0].a_status == 'FAIL'


def test_original_function_comment_is_not_rewritten():
    result = inspect_file('int f(void){ /* 中文 */ return 1; }')
    assert '中文' in result.candidates[0].source_text


def test_cli_file_report(tmp_path):
    import json
    from codeart.cli import main
    src = tmp_path / 'input.c'
    output = tmp_path / 'output.c'
    report = tmp_path / 'report.json'
    src.write_text('#include <stdio.h>\nint f(int x){return x+1;}\n')
    assert main(['--file', str(src), '--function', 'f', '--output', str(output), '--report', str(report)]) == 0
    data = json.loads(report.read_text())
    assert data['prepass']['selected'] == 'f'
    assert data['prepass']['ignored_lines'][0]['start_line'] == 1
    assert data['code_fill_ratio'] == data['coverage']['token']
    assert data['code_fill_ratio'] < 0.1
    assert data['code_fill_warning']
    assert output.exists()


def test_web_prepass_endpoint():
    import json
    from threading import Thread
    from urllib.request import Request, urlopen
    from codeart.app import create_server
    server = create_server(0)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        payload = json.dumps({'source': '#include <stdio.h>\nint f(int x){return x;}'}).encode()
        request = Request(f'http://127.0.0.1:{server.server_port}/api/prepass', data=payload, headers={'Content-Type': 'application/json'})
        with urlopen(request) as response:
            data = json.load(response)
        assert data['selected'] == 'f'
        assert 'not the entire input program' in data['validation_scope']
    finally:
        server.shutdown()
        server.server_close()
        server.jobs.shutdown()
        worker.join()
