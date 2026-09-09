# Run: uv run --with pyyaml==6.0.2 python -B -m unittest discover -s topic-research/tests -v

import contextlib
import datetime as dt
import importlib.util
import io
import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'research.py'
SPEC = importlib.util.spec_from_file_location('research_tool', SCRIPT)
assert SPEC and SPEC.loader
research = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research)


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.kb = self.root / 'research'
        self.today = dt.datetime.now(dt.timezone.utc).date()
        self.assertEqual(self.run_tool('init', self.kb)[0], 0)

    def run_tool(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = research.main([str(arg) for arg in args])
        return status, stdout.getvalue(), stderr.getvalue()

    def source(self, slug='source', body=None, **changes):
        data = dict(slug=slug, title='Source title', url=f'https://example.org/{slug}',
                    site='example.org', type='review', party='independent', retrieved=str(self.today),
                    added=str(self.today), candidate_id='R1-N001', lane='reviews', relevance='Decision evidence')
        data.update(changes)
        if body is None:
            body = '## Summary\nAn independent review.\n\n## Quotes\n- q1: "First fact" — opening\n- q2: "Second fact" — conclusion\n\n## Notes\nContext.\n'
        return self.note('sources', slug, data, body)

    def subject(self, slug='widget', body='A tool. [[source#q1]]', **changes):
        data = dict(slug=slug, name='Widget', kind='tool',
                    added=str(self.today), updated=str(self.today))
        data.update(changes)
        return self.note('subjects', slug, data, body)

    def note(self, directory, slug, data, body):
        path = self.kb / directory / f'{slug}.md'
        path.write_text('---\n' + yaml.safe_dump(data) + '---\n' + body, encoding='utf-8')
        return path

    def assert_error(self, fragment):
        status, output, _ = self.run_tool('check', self.kb)
        self.assertEqual(status, 1, output)
        self.assertIn('ERROR:', output)
        self.assertIn(fragment, output)
        self.assertIn('KB_CHECK=errors=', output)
        return output

    def test_url_normalization(self):
        cases = {
            'HTTPS://WWW.Example.COM/Path/': 'https://example.com/Path',
            'https://example.com': 'https://example.com/',
            'https://example.com/': 'https://example.com/',
            'https://www.example.com/?utm_source=x': 'https://example.com/',
            'https://www.www.example.com/a': 'https://example.com/a',
            'https://example.com?': 'https://example.com/',
            'https://example.com/a//': 'https://example.com/a',
            'http://WWW.example.com:80/a#part': 'http://example.com/a',
            'https://example.com:443/a/?utm_source=x&gclid=1&fbclid=2&ref=3&si=4&mc_cid=5&mc_eid=6': 'https://example.com/a',
            'https://example.com:8443/Aa/?q=a%20b&x=1&x=2&empty=&UTM_MEDIUM=y': 'https://example.com:8443/Aa?q=a%20b&x=1&x=2&empty=',
            'http://[::1]:80/': 'http://[::1]/',
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(research.normalize_url(raw), expected)
                self.assertEqual(research.normalize_url(research.normalize_url(raw)), expected)
        for raw in ('/path', 'ftp://example.com', 'https:///path', 'https://', 'http://a:bad', 'http://[broken', None, 'https://a b/', 'https://user:secret@example.com'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                research.normalize_url(raw)

    def test_dedup(self):
        self.source(url='https://www.example.org/product/?utm_source=old')
        lanes = [
            [dict(url='HTTPS://www.Example.org/product/#a', title='First', site='wrong.example', subject='', lane='b', relevance='Short', extra=42),
             dict(url='broken', title='Bad', id='stale-id')],
            [dict(url='https://example.org/product?ref=feed', title='Later', subject='My Product!', lane='a', relevance='Much longer relevance'),
             dict(url='https://example.org/details', title='Details', subject='my-product', lane='a', relevance='Details'),
             dict(url='https://example.org/product', subject='Different Product', lane='b', relevance='Tiny')],
        ]
        paths = []
        for i, records in enumerate(lanes):
            path = self.root / f'lane-{i}.jsonl'
            path.write_text(''.join(json.dumps(row) + '\n' for row in records))
            paths.append(path)
        out = self.root / 'candidates.jsonl'
        args = ('dedup', '--kb', self.kb, '--prefix', 'run-R1', '--out', out, *paths)
        status, output, _ = self.run_tool(*args)
        self.assertEqual(status, 0, output)
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        first, invalid, second = rows
        self.assertEqual(first['id'], 'run-R1-N001')
        self.assertEqual(first['lanes'], ['a', 'b'])
        self.assertEqual(first['relevance'], 'Much longer relevance')
        self.assertEqual((first['title'], first['extra']), ('First', 42))
        self.assertEqual(first['url'], 'https://example.org/product')
        self.assertEqual(first['site'], 'example.org')
        self.assertTrue(first['in_kb'])
        self.assertEqual(first['slug'], 'source')
        self.assertEqual(first['subject_group'], 'myproduct')
        self.assertEqual(second['subject_group'], first['subject_group'])
        self.assertEqual(second['id'], 'run-R1-N002')
        self.assertFalse(second['in_kb'])
        self.assertIn('error', invalid)
        self.assertNotIn('id', invalid)
        self.assertIn('INPUT=5 CANDIDATES=2 COLLAPSED=2 IN_KB=1 INVALID=1', output)
        before = out.read_bytes()
        self.run_tool(*args)
        self.assertEqual(out.read_bytes(), before)

    def test_dedup_first_nonempty_subject_key(self):
        lane, out = self.root / 'lane.jsonl', self.root / 'candidates.jsonl'
        records = [
            dict(url='https://example.org/tool', subject='日本語', lane='a'),
            dict(url='https://example.org/tool', subject='Nihongo Tool', lane='b'),
        ]
        lane.write_text(''.join(json.dumps(record) + '\n' for record in records))
        status, output, _ = self.run_tool('dedup', '--kb', self.kb, '--prefix', 'R1', '--out', out, lane)
        self.assertEqual(status, 0, output)
        candidate = json.loads(out.read_text())
        self.assertEqual(candidate['subject_group'], 'nihongotool')

    def test_dedup_round_trip_and_source_errors(self):
        lane, out = self.root / 'lane.jsonl', self.root / 'candidates.jsonl'
        args = ('dedup', '--kb', self.kb, '--prefix', 'R1', '--out', out, lane)
        for url in ('https://www.example.org?utm_source=sweep', 'https://example.org/a//'):
            with self.subTest(url=url):
                lane.write_text(json.dumps(dict(url=url, title='Candidate', lane='sweep')) + '\n')
                self.assertEqual(self.run_tool(*args)[0], 0)
                emitted = json.loads(out.read_text())
                path = self.source(url=emitted['url'])
                path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes())
                self.assertEqual(self.run_tool(*args)[0], 0)
                matched = json.loads(out.read_text())
                self.assertTrue(matched['in_kb'])
                self.assertEqual(matched['slug'], 'source')
        for content in (b'\xff', b'No frontmatter'):
            path.write_bytes(content)
            status, _, stderr = self.run_tool(*args)
            self.assertEqual(status, 1)
            self.assertIn(f'ERROR: {path}:', stderr)
        self.source(url='not-a-url')
        status, _, stderr = self.run_tool(*args)
        self.assertEqual(status, 1)
        self.assertIn(f'ERROR: {path}:', stderr)

    def test_guarded_markdown_reads(self):
        source = self.source()
        source.write_bytes(b'\xef\xbb\xbf' + source.read_bytes())
        with mock.patch.object(research, 'read_markdown', wraps=research.read_markdown) as read:
            self.assertEqual(self.run_tool('check', self.kb)[0], 0)
        self.assertEqual([call.args[0] for call in read.call_args_list].count(source), 1)
        path = self.kb / 'runs' / 'bad.md'
        path.write_bytes(b'\xff')
        output = self.assert_error(f'{path}:')
        for counter in ('SINGLE_PARTY', 'UNCITED', 'NO_QUOTES', 'STALE'):
            self.assertIn(f'{counter}=', output)
        path.write_text('Readable but unavailable for this test.')
        original = research.read_markdown

        def unreadable(candidate):
            if candidate == path:
                raise PermissionError('permission denied')
            return original(candidate)

        with mock.patch.object(research, 'read_markdown', side_effect=unreadable):
            self.assert_error(f'{path}: permission denied')

    def test_frontmatter_and_enums(self):
        path = self.source()
        for content in ('No frontmatter', '---\n[one, two]\n---\n', '---\nslug: [\n---\n', '---\nx: !!python/object:object {}\n---\n'):
            with self.subTest(content=content):
                path.write_text(content)
                self.assert_error('ERROR:')
        for field, value in [('title', ''), ('lane', None), ('relevance', []), ('slug', 'wrong'), ('type', 'bad'), ('party', 'bad'), ('access', 'bad')]:
            with self.subTest(field=field):
                if field == 'slug':
                    path = self.source()
                    path.write_text(path.read_text().replace('slug: source', 'slug: wrong'))
                else:
                    self.source(**{field: value})
                self.assert_error(field)
        self.source()
        for field in ('name', 'kind', 'updated'):
            with self.subTest(field=field):
                self.subject(**{field: ''})
                self.assert_error(field)
        for kind, message in ((None, 'missing or empty kind'), ('   ', 'missing or empty kind'),
                              (42, 'kind must be a non-empty string'),
                              (['tool'], 'kind must be a non-empty string')):
            with self.subTest(kind=kind):
                self.subject(kind=kind)
                self.assert_error(message)
        self.subject(kind='argument')
        self.assertEqual(self.run_tool('check', self.kb)[0], 0)
        self.subject()
        data, body = research.read_note(path)
        del data['candidate_id']
        self.note('sources', 'source', data, body)
        self.assert_error('candidate_id')

    def test_dates(self):
        yesterday, tomorrow = self.today - dt.timedelta(days=1), self.today + dt.timedelta(days=1)
        cases = [({'retrieved': '2025-2-01'}, 'invalid retrieved'),
                 ({'published': '2025-02-30'}, 'invalid published'),
                 ({'added': str(tomorrow)}, 'added is after today'),
                 ({'retrieved': str(tomorrow)}, 'retrieved is after today'),
                 ({'retrieved': str(yesterday), 'published': str(self.today)}, 'published is after retrieved'),
                 ({'retrieved': str(yesterday), 'updated': str(self.today)}, 'updated is after retrieved')]
        for changes, message in cases:
            with self.subTest(changes=changes):
                self.source(**changes)
                self.assert_error(message)
        self.source(retrieved=self.today)  # YAML's native date value is accepted.
        self.subject(added=str(tomorrow))
        self.assert_error('added is after today')
        self.subject(updated='unknown')
        self.assert_error('invalid updated')

    def test_url_and_site(self):
        for url in ('/relative', 'ftp://example.org', 'https:///missing'):
            with self.subTest(url=url):
                self.source(url=url)
                self.assert_error('URL must be absolute')
        self.source(site='www.example.org')
        self.assert_error('site does not match')
        self.source(url='https://WWW.Example.org:443/source')
        self.assertEqual(self.run_tool('check', self.kb)[0], 0)

    def test_duplicate_url(self):
        self.source()
        self.source('other', url='https://www.example.org:443/source/?utm_source=x#q')
        self.assert_error('duplicate URL')

    def test_duplicate_slug(self):
        self.source()
        self.subject('source', body='[[source]]')
        self.assert_error('duplicate slug')

    def test_malformed_quotes(self):
        for entries in ('-', '-   ', '*', '+', '- q: "Text" — here', '- q0: "Text" — here', '* q1: "Text" — here',
                        '- q1: Text — here', '- q1: "Text" - here',
                        '- q1: "Text" — here\n- q1: "Again" — there',
                        '- q2: "Text" — here', '- q2: "Text" — here\n- q1: "Again" — there'):
            with self.subTest(entries=entries):
                self.source(body='## Quotes\n' + entries + '\n## Notes\n- Ordinary note')
                self.assert_error('Quotes')

    def test_quotes_end_at_any_heading(self):
        for level in range(1, 7):
            with self.subTest(level=level):
                self.source(body='## Quotes\n- q1: "A fact" — opening\n'
                            + '#' * level + ' Notes\n- An ordinary note\n- q2: "Not a quote anchor" — notes\n')
                self.assertEqual(self.run_tool('check', self.kb)[0], 0)
                topic = self.kb / 'topics' / 'topic.md'
                topic.write_text('[[source#q2]]')
                self.assert_error('invalid quote anchor')
                topic.unlink()

    def test_citations_and_anchors(self):
        self.source(note='[[missing-in-metadata]]')
        self.assert_error('[[missing-in-metadata]]')
        path = self.source()
        path.write_text(path.read_text() + '\n- q3: "Outside the Quotes section" — notes\n')
        self.subject()
        for directory in research.DIRECTORIES:
            path = self.kb / directory / 'nested' / 'note.md'
            path.parent.mkdir()
            for citation in ('[[missing]]', '[[source#q]]', '[[source#q3]]', '[[widget#q1]]', '[[source#q01]]'):
                with self.subTest(directory=directory, citation=citation):
                    path.write_text(citation)
                    self.assert_error(citation)
            path.unlink()
        (self.kb / 'topics' / 'good.md').write_text('[[widget]] [[source]] [[source#q2]]')
        self.assertEqual(self.run_tool('check', self.kb)[0], 0)

    def test_subject_without_source_citations(self):
        self.source()
        path = self.subject(body='No evidence. [[widget]]', note='[[source]]')
        self.assert_error(f'{path}: subject has no source citations')
        self.subject(body='Evidence. [[source#q2]]')
        self.assertEqual(self.run_tool('check', self.kb)[0], 0)

    def test_structure_and_symlinks(self):
        missing = self.run_tool('check', self.root / 'missing')
        self.assertEqual(missing[0], 1)
        link = self.root / 'alias'
        link.symlink_to(self.kb, target_is_directory=True)
        self.assertEqual(self.run_tool('check', link)[0], 1)
        for directory in research.DIRECTORIES:
            path = self.kb / directory
            moved = self.root / directory
            path.rename(moved)
            self.assert_error('must be a directory')
            path.symlink_to(moved, target_is_directory=True)
            self.assert_error('symlink')
            path.unlink()
            moved.rename(path)
        for relative, target in [('index.md', self.root / 'outside'), ('topics/alias', self.root), ('AGENTS.md', './README.md'), ('topics/nested.md', '../README.md')]:
            with self.subTest(relative=relative):
                path = self.kb / relative
                path.unlink(missing_ok=True)
                path.symlink_to(target)
                self.assert_error('symlinks are not allowed')
                path.unlink()
        self.assertFalse((self.root / 'outside').exists())

    def test_warning_counters(self):
        self.source(party='community', retrieved=str(self.today - dt.timedelta(days=181)))
        self.subject()
        self.source('orphan', body='## Summary\nNo quotes section.')
        self.source('empty', body='## Quotes\n\n## Notes\n- Just a note.', retrieved=str(self.today - dt.timedelta(days=180)))
        (self.kb / 'runs' / 'run.md').write_text('[[orphan]]')
        status, output, _ = self.run_tool('check', self.kb)
        self.assertEqual(status, 0, output)
        self.assertEqual(output.splitlines()[-5:], ['KB_CHECK=ok', 'SINGLE_PARTY=1', 'UNCITED=2', 'NO_QUOTES=2', 'STALE=1'])
        self.assertEqual(output.count('WARNING:'), 6)
        self.assertIn('widget: cited sources all have party community', output)
        (self.kb / 'topics' / 'topic.md').write_text('[[orphan]]')
        self.subject(body='[[source]] [[empty]]')
        output = self.run_tool('check', self.kb)[1]
        self.assertIn('SINGLE_PARTY=0', output)
        self.assertIn('UNCITED=0', output)

    def test_data_synthesis_without_subjects(self):
        self.source(type='data', party='independent')
        (self.kb / 'topics' / 'estimate.md').write_text('Reported estimate. [[source#q1]]')
        self.assertEqual(list((self.kb / 'subjects').glob('*.md')), [])
        index = self.kb / 'index.md'
        index.write_text('sentinel')
        status, output, _ = self.run_tool('check', self.kb)
        self.assertEqual(status, 0, output)
        self.assertIn('KB_CHECK=ok', output)
        self.assertIn('SINGLE_PARTY=0', output)
        self.assertIn('UNCITED=0', output)
        content = index.read_text()
        self.assertNotIn('sentinel', content)
        self.assertIn('## Subjects', content)
        self.assertIn('## Sources', content)
        subjects = content.split('## Subjects', 1)[1].split('## Sources', 1)[0]
        self.assertEqual([line for line in subjects.splitlines() if line.startswith('|')],
                         ['| Name | Kind | Sources |', '| --- | --- | --- |'])

    def test_index_clean_only_and_stable(self):
        self.source('z', party='community', type='forum')
        self.source('a', party='interested', type='reference')
        self.subject(body='[[a#q1]] [[z]] [[z#q2]]')
        index = self.kb / 'index.md'
        index.write_text('sentinel')
        bad = self.kb / 'topics' / 'bad.md'
        bad.write_text('[[absent]]')
        self.assert_error('absent')
        self.assertEqual(index.read_text(), 'sentinel')
        index.unlink()
        self.assert_error('absent')
        self.assertFalse(index.exists())
        bad.unlink()
        self.assertEqual(self.run_tool('check', self.kb)[0], 0)
        content = index.read_bytes()
        self.assertIn('| tool | 2 |', content.decode())
        self.assertLess(content.index(b'## Subjects'), content.index(b'## Sources'))
        self.assertLess(content.index(b'### community / forum'), content.index(b'### interested / reference'))
        self.run_tool('check', self.kb)
        self.assertEqual(index.read_bytes(), content)

    def test_init(self):
        self.assertEqual((self.kb / 'index.md').read_bytes(), b'')
        for name in ('AGENTS.md', 'CLAUDE.md'):
            self.assertEqual((self.kb / name).readlink(), Path('README.md'))
        for name in research.DIRECTORIES:
            self.assertTrue((self.kb / name / '.gitkeep').is_file())
        self.assertTrue((self.kb / 'scope.md').is_file())
        for path in (self.kb, self.root / 'broken-link', self.root / 'no-parent' / 'kb'):
            if path.name == 'broken-link':
                path.symlink_to(self.root / 'absent')
            status, _, stderr = self.run_tool('init', path)
            self.assertEqual(status, 1)
            self.assertTrue(stderr.startswith('ERROR:'))
        project = self.root / 'project'
        project.mkdir()
        ignore = project / '.gitignore'
        original = b'existing\r\n'
        ignore.write_bytes(original)
        child = project / 'second'
        status, output, _ = self.run_tool('init', child)
        self.assertEqual(status, 0)
        self.assertEqual(output, f'INITIALIZED={child}\n')
        self.assertEqual(ignore.read_bytes(), original)
        self.assertEqual(list(project.rglob('.gitignore')), [ignore])
        ignore.unlink()
        self.assertEqual(self.run_tool('init', project / 'third')[0], 0)
        self.assertEqual(list(project.rglob('.gitignore')), [])

    def test_links_skip_offline_errors(self):
        self.source(type='bad')
        with mock.patch.object(research, 'urlopen') as fetch:
            status, output, _ = self.run_tool('check', self.kb, '--links')
        self.assertEqual(status, 1)
        self.assertIn('KB_CHECK=errors=', output)
        self.assertIn('LINK_FAILURES=0', output)
        fetch.assert_not_called()

    def test_links_invalid_http_status_line(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(5)

            def respond():
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5)
                    connection.recv(4096)
                    connection.sendall(b'NOT-HTTP\r\n\r\n')

            thread = threading.Thread(target=respond, daemon=True)
            thread.start()
            try:
                path = self.source(url=f'http://127.0.0.1:{listener.getsockname()[1]}/', site='127.0.0.1')
                before = path.read_bytes()
                status, output, stderr = self.run_tool('check', self.kb, '--links')
                self.assertEqual(status, 0, stderr)
                self.assertIn('WARNING: link ', output)
                self.assertIn('NOT-HTTP', output)
                self.assertIn('KB_CHECK=ok', output)
                self.assertIn('LINK_FAILURES=1', output)
                self.assertEqual(path.read_bytes(), before)
            finally:
                thread.join(timeout=6)

    def test_links(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, self.headers.get('User-Agent')))
                self.send_response(404 if self.path == '/missing' else 302 if self.path.startswith('/redirect') else 200)
                if self.path.startswith('/redirect'):
                    self.send_header('Location', '/ok')
                self.end_headers()

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            # Reserve a port without listening, so connection refusal is deterministic.
            with socket.socket() as unused:
                unused.bind(('127.0.0.1', 0))
                dead = f'http://127.0.0.1:{unused.getsockname()[1]}/dead'
                paths = [self.source(slug, url=url, site='127.0.0.1') for slug, url in
                         [('ok', base + '/redirect?ref=original'), ('missing', base + '/missing'), ('dead', dead)]]
                before = {p: p.read_bytes() for p in paths}
                status, offline, _ = self.run_tool('check', self.kb)
                self.assertEqual(status, 0)
                self.assertEqual(requests, [])
                self.assertNotIn('LINK_FAILURES', offline)
                with mock.patch.object(research, 'urlopen', wraps=research.urlopen) as fetch:
                    status, output, _ = self.run_tool('check', self.kb, '--links')
                self.assertEqual(status, 0, output)
                self.assertIn('LINK_FAILURES=2', output)
                self.assertEqual(output.count('WARNING: link '), 2)
                self.assertIn('404', output)
                self.assertEqual(sorted(p for p, _ in requests), ['/missing', '/ok', '/redirect?ref=original'])
                self.assertTrue(all('topic-research' in ua for _, ua in requests))
                self.assertEqual(fetch.call_count, 3)
                self.assertTrue(all(call.kwargs['timeout'] == 30 for call in fetch.call_args_list))
                self.assertEqual({p: p.read_bytes() for p in paths}, before)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
