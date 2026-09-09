#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.2"]
# ///
"""Initialize, deduplicate, and validate a topic research knowledge base."""

import argparse
import datetime as dt
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit, urlunsplit, unquote_plus
from urllib.request import Request, urlopen

import yaml


FRONT = re.compile(r'\A---\s*\n(.*?)\n---(?:\s*\n|\s*\Z)', re.DOTALL)
CITATION = re.compile(r'\[\[([^\[\]\n]+)\]\]')
QUOTE = re.compile(r'- q([1-9][0-9]*): "(.+)" — (\S.*)')
DIRECTORIES = ('sources', 'subjects', 'topics', 'runs')
SOURCE_REQUIRED = 'slug title url site type party retrieved added candidate_id lane relevance'.split()
SUBJECT_REQUIRED = 'slug name kind added updated'.split()
ENUMS = {
    'type': 'reference directory article news review forum social video data other'.split(),
    'party': ['interested', 'independent', 'community'], 'access': ['public', 'restricted'],
}


def normalize_url(value):
    if not isinstance(value, str) or re.search(r'\s', value):
        raise ValueError('URL must be absolute http/https with a host')
    parts = urlsplit(value)
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname:
        raise ValueError('URL must be absolute http/https with a host')
    scheme, host, port = parts.scheme.lower(), parts.hostname.lower(), parts.port
    host = re.sub(r'^(?:www\.)+', '', host)
    if not host or parts.username is not None or parts.password is not None:
        raise ValueError('URL must have a host and no credentials')
    authority = f'[{host}]' if ':' in host else host
    if port is not None and (scheme, port) not in (('http', 80), ('https', 443)):
        authority += f':{port}'
    query = []
    for item in parts.query.split('&'):
        key = unquote_plus(item.split('=', 1)[0]).lower()
        if item and not key.startswith('utm_') and key not in {'gclid', 'fbclid', 'ref', 'si', 'mc_cid', 'mc_eid'}:
            query.append(item)
    path = parts.path.rstrip('/') or '/'
    return urlunsplit((scheme, authority, path, '&'.join(query), ''))


def read_markdown(path):
    return path.read_text(encoding='utf-8-sig')


def read_note(path, content=None):
    if content is None:
        content = read_markdown(path)
    match = FRONT.match(content)
    if not match:
        raise ValueError('missing YAML frontmatter')
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError('frontmatter is not a mapping')
    return data, content[match.end():]


def read_jsonl(path):
    records = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'{path}:{number}: malformed JSON: {exc.msg}') from exc
        if not isinstance(record, dict):
            raise ValueError(f'{path}:{number}: candidate must be a JSON object')
        records.append(record)
    return records


def structure_errors(kb):
    errors = []
    for path in [kb, *(kb / name for name in DIRECTORIES)]:
        if path.is_symlink() or not path.is_dir():
            errors.append(f'{path}: must be a directory, not a symlink')
    if kb.is_dir() and not kb.is_symlink():
        for path in sorted(kb.rglob('*')):
            if path.is_symlink() and not (
                path.parent == kb and path.name in ('AGENTS.md', 'CLAUDE.md')
                and os.readlink(path) == 'README.md'
            ):
                errors.append(f'{path}: symlinks are not allowed')
    return errors


def command_init(args):
    kb = args.kb.absolute()
    if kb.exists() or kb.is_symlink() or not kb.parent.is_dir():
        raise ValueError(f'{kb}: path exists, is a symlink, or parent is not a directory')
    template = Path(__file__).resolve().parents[1] / 'assets' / 'kb-template'
    shutil.copytree(template, kb, symlinks=True)
    (kb / 'index.md').write_text('', encoding='utf-8')
    print(f'INITIALIZED={kb}')
    return 0


def command_dedup(args):
    errors = structure_errors(args.kb)
    if errors:
        raise ValueError('\n'.join(errors))
    known = {}
    for path in sorted((args.kb / 'sources').glob('*.md')):
        try:
            data, _ = read_note(path)
            known[normalize_url(data.get('url'))] = data.get('slug', path.stem)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            raise ValueError(f'{path}: {exc}') from exc
    inputs = [record for path in args.lanes for record in read_jsonl(path)]
    merged, output, subject_groups = {}, [], {}
    invalid = 0
    for original in inputs:
        record = dict(original)
        try:
            url = normalize_url(record.get('url'))
        except ValueError as exc:
            record.pop('id', None)
            record['error'] = str(exc)
            output.append(record)
            invalid += 1
            continue
        lane = str(record.get('lane', '')).strip()
        relevance = str(record.get('relevance') or '')
        subject = str(record.get('subject') or '').strip()
        if subject and not subject_groups.get(url):
            subject_groups[url] = re.sub('[^a-z0-9]', '', subject.lower())
        if url in merged:
            item = merged[url]
            item['lanes'] = sorted(set(item['lanes']) | ({lane} if lane else set()))
            if len(relevance) > len(item['relevance']):
                item['relevance'] = relevance
            continue
        record.update(url=url, id=f'{args.prefix}-N{len(merged) + 1:03d}',
                      lanes=[lane] if lane else [], relevance=relevance, in_kb=url in known)
        record['site'] = urlsplit(url).hostname
        if url in known:
            record['slug'] = known[url]
        merged[url] = record
        output.append(record)
    for url, record in merged.items():
        if subject_groups.get(url):
            record['subject_group'] = subject_groups[url]
    args.out.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in output), encoding='utf-8')
    for row in output:
        print(f"{row.get('id', 'INVALID')} in_kb={str(row.get('in_kb', False)).lower()} "
              f"{('subject_group=' + row['subject_group'] + ' ') if row.get('subject_group') else ''}"
              f"{row.get('site', '')} {row.get('title', '')}")
    print(f'INPUT={len(inputs)} CANDIDATES={len(merged)} COLLAPSED={len(inputs) - len(merged) - invalid} '
          f'IN_KB={sum(row["in_kb"] for row in merged.values())} INVALID={invalid}')
    return 0


def quote_ids(body, path, errors):
    numbers, in_quotes = [], False
    for line in body.splitlines():
        if re.match(r'^#{1,6}(?:\s|$)', line):
            in_quotes = line.strip() == '## Quotes'
        elif in_quotes and re.match(r'^\s*[-*+](?:\s|$)', line):
            match = QUOTE.fullmatch(line)
            if not match:
                errors.append(f'{path}: malformed Quotes entry: {line}')
            else:
                numbers.append(int(match[1]))
    if numbers != list(range(1, len(numbers) + 1)):
        errors.append(f'{path}: Quotes must be numbered q1..qN in order without duplicates')
    return {f'q{number}' for number in numbers}


def validate_record(data, path, source, today, errors):
    for key in SOURCE_REQUIRED if source else SUBJECT_REQUIRED:
        if not data.get(key) or not str(data[key]).strip():
            errors.append(f'{path}: missing or empty {key}')
    if not source and 'kind' in data and not isinstance(data['kind'], str):
        errors.append(f'{path}: kind must be a non-empty string')
    if data.get('slug') != path.stem:
        errors.append(f'{path}: slug must equal filename stem')
    if source:
        for key in ('type', 'party', 'access'):
            if key in data and data[key] not in ENUMS[key]:
                errors.append(f'{path}: invalid {key}')
    dates = {}
    for key in ('retrieved', 'added', 'published', 'updated'):
        if key not in data:
            continue
        value = str(data[key])
        try:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
                raise ValueError()
            dates[key] = dt.date.fromisoformat(value)
        except ValueError:
            errors.append(f'{path}: invalid {key} date; expected YYYY-MM-DD')
    for key in ('retrieved', 'added'):
        if key in dates and dates[key] > today:
            errors.append(f'{path}: {key} is after today')
    if source and 'retrieved' in dates:
        for key in ('published', 'updated'):
            if key in dates and dates[key] > dates['retrieved']:
                errors.append(f'{path}: {key} is after retrieved')
    return dates


def write_index(kb, sources, subjects, subject_sources):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    lines = ['# Research index', '', '## Subjects', '',
             '| Name | Kind | Sources |', '| --- | --- | --- |']
    for slug, data in sorted(subjects.items()):
        lines.append(f'| [{cell(data["name"])}](subjects/{slug}.md) | {cell(data["kind"])} | '
                     f'{len(subject_sources[slug])} |')
    lines.extend(['', '## Sources'])
    group = None
    for slug, data in sorted(sources.items(), key=lambda pair: (pair[1]['party'], pair[1]['type'], pair[0])):
        current = (data['party'], data['type'])
        if current != group:
            lines.extend(['', f'### {current[0]} / {current[1]}', '',
                          '| Site | Retrieved | Title |', '| --- | --- | --- |'])
            group = current
        lines.append(f'| {cell(data["site"])} | {data["retrieved"]} | '
                     f'[{cell(data["title"])}](sources/{slug}.md) |')
    (kb / 'index.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def command_check(args):
    kb, today = args.kb.absolute(), dt.datetime.now(dt.timezone.utc).date()
    errors, warnings = structure_errors(kb), []
    counts = dict.fromkeys(('SINGLE_PARTY', 'UNCITED', 'NO_QUOTES', 'STALE'), 0)
    sources, subjects, quotes, urls, bodies = {}, {}, {}, {}, {}
    contents = {}
    link_urls = set()

    def warn(counter, message):
        counts[counter] += 1
        warnings.append(message)

    # Do not traverse or write through an unsafe structure.
    if not errors:
        for directory, records in (('sources', sources), ('subjects', subjects)):
            for path in sorted((kb / directory).glob('*.md')):
                contents[path] = None
                try:
                    contents[path] = read_markdown(path)
                    data, body = read_note(path, contents[path])
                except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
                    errors.append(f'{path}: {exc}')
                    continue
                slug, source = path.stem, directory == 'sources'
                dates = validate_record(data, path, source, today, errors)
                if slug in sources or slug in subjects:
                    errors.append(f'{path}: duplicate slug {slug}')
                records[slug], bodies[path] = data, body
                if not source:
                    continue
                quotes[slug] = quote_ids(body, path, errors)
                if not quotes[slug]:
                    warn('NO_QUOTES', f'{slug}: no quotes')
                if 'retrieved' in dates and (today - dates['retrieved']).days > 180:
                    warn('STALE', f'{slug}: retrieved more than 180 days ago')
                try:
                    url = normalize_url(data.get('url'))
                    link_urls.add(data['url'])
                    if data.get('site') != urlsplit(url).hostname:
                        errors.append(f'{path}: site does not match normalized URL host')
                    if url in urls:
                        errors.append(f'{path}: duplicate URL with {urls[url]}')
                    urls[url] = slug
                except ValueError as exc:
                    errors.append(f'{path}: {exc}')
        cited, subject_sources = set(), {slug: set() for slug in subjects}
        for directory in DIRECTORIES:
            for path in sorted((kb / directory).rglob('*.md')):
                if not path.is_file():
                    continue
                try:
                    content = contents[path] if path in contents else read_markdown(path)
                except (OSError, UnicodeError) as exc:
                    errors.append(f'{path}: {exc}')
                    continue
                if content is None:
                    continue
                body_references = set(CITATION.findall(bodies.get(path, content)))
                for reference in CITATION.findall(content):
                    slug, separator, anchor = reference.partition('#')
                    if slug not in sources and slug not in subjects:
                        errors.append(f'{path}: unresolved citation [[{reference}]]')
                        continue
                    if separator and (slug not in sources or anchor not in quotes.get(slug, set())):
                        errors.append(f'{path}: invalid quote anchor [[{reference}]]')
                        continue
                    if reference in body_references and slug in sources and directory in ('subjects', 'topics'):
                        cited.add(slug)
                        if path.parent == kb / 'subjects' and path.stem in subjects:
                            subject_sources[path.stem].add(slug)
        for slug in sources:
            if slug not in cited:
                warn('UNCITED', f'{slug}: not cited from a subject or topic')
        for slug, citations in subject_sources.items():
            if not citations:
                errors.append(f'{kb / "subjects" / (slug + ".md")}: subject has no source citations in its body')
            else:
                parties = {str(sources[item].get('party')) for item in citations}
                if len(parties) == 1:
                    warn('SINGLE_PARTY', f'{slug}: cited sources all have party {parties.pop()}')
        if not errors:
            write_index(kb, sources, subjects, subject_sources)
    if args.links:
        counts['LINK_FAILURES'] = 0
        for url in sorted(link_urls) if not errors else []:
            try:
                request = Request(url, headers={'User-Agent': 'topic-research/1.0 (source link checker)'})
                with urlopen(request, timeout=30) as response:
                    if not 200 <= response.status < 300:
                        raise ValueError(f'HTTP {response.status}')
            except (HTTPException, OSError, ValueError) as exc:
                warn('LINK_FAILURES', f'link {url}: {exc}')
    for error in errors:
        print(f'ERROR: {error}')
    for warning in warnings:
        print(f'WARNING: {warning}')
    print(f'KB_CHECK=errors={len(errors)}' if errors else 'KB_CHECK=ok')
    for name, count in counts.items():
        print(f'{name}={count}')
    return int(bool(errors))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('kb', type=Path)
    dedup = commands.add_parser('dedup')
    dedup.add_argument('--kb', type=Path, required=True)
    dedup.add_argument('--prefix', required=True)
    dedup.add_argument('--out', type=Path, required=True)
    dedup.add_argument('lanes', type=Path, nargs='+')
    check = commands.add_parser('check')
    check.add_argument('kb', type=Path)
    check.add_argument('--links', action='store_true')
    args = parser.parse_args(argv)
    try:
        return {'init': command_init, 'dedup': command_dedup, 'check': command_check}[args.command](args)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
