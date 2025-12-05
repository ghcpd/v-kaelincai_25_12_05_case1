import json
import time
import subprocess
import sys
import xml.etree.ElementTree as ET

RESULTS = {'start': int(time.time()), 'results': [], 'metrics': {}}

if __name__ == '__main__':
    cmd = [sys.executable, '-m', 'pytest', '-q', '--disable-warnings', '--maxfail=1', '--junitxml=results/one_click_pytest.xml']
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    with open('results/one_click_output.txt', 'w', encoding='utf-8') as out:
        out.write(proc.stdout)
        out.write('\nSTDERR:\n')
        out.write(proc.stderr)
    RESULTS['end'] = int(time.time())
    RESULTS['duration'] = RESULTS['end'] - RESULTS['start']
    RESULTS['metrics']['exit_code'] = proc.returncode
    # parse junit xml if present
    try:
        tree = ET.parse('results/one_click_pytest.xml')
        root = tree.getroot()
        suite = root.find('testsuite')
        if suite is not None:
            tests = int(suite.attrib.get('tests', 0))
            failures = int(suite.attrib.get('failures', 0))
            errors = int(suite.attrib.get('errors', 0))
            skipped = int(suite.attrib.get('skipped', 0))
            RESULTS['metrics'].update({'tests': tests, 'failures': failures, 'errors': errors, 'skipped': skipped})
            RESULTS['metrics']['passed'] = tests - failures - errors - skipped
        else:
            RESULTS['metrics']['parse_error'] = 'no testsuite element found'
    except Exception as e:
        RESULTS['metrics']['parse_error'] = repr(e)
    with open('results/one_click_results.json', 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, indent=2)
    print('One-click results written to results/one_click_results.json')
