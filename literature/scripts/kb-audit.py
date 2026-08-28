#!/usr/bin/env python3
"""Bracket KB writes for verification.

The audit attributes all changes in an interval to that interval, not to a
specific process. Anything the lead changes between ``before`` and ``after`` is
indistinguishable from writer activity, so the lead must not modify the project
during the bracket.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys


STATE_FILE = "before.json"


class AuditError(Exception):
    """A user-facing audit failure."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise AuditError(message)


def fail(reason):
    reason = flatten(reason)
    print(f"ERROR={reason}")
    return 1


def flatten(value):
    return " ".join(str(value).splitlines()).strip() or "unknown error"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def resolve_project(path):
    project = os.path.realpath(path)
    if not os.path.isdir(project):
        raise AuditError(f"project is not a directory: {path}")
    return project


def kb_path(project):
    return os.path.join(project, "literature")


def validate_kb_for_before(project):
    kb = kb_path(project)
    if os.path.islink(kb):
        raise AuditError(f"knowledge-base path is a symlink: {kb}")
    if not os.path.isdir(kb):
        raise AuditError(f"knowledge base is missing: {kb}")
    return kb


def is_within(path, directory):
    try:
        return os.path.commonpath((directory, path)) == directory
    except ValueError:
        return False


def resolve_state_dir(path, project, git_root=None):
    state_dir = os.path.realpath(path)
    if is_within(state_dir, project):
        raise AuditError(f"state directory is inside the project: {state_dir}")
    if git_root and is_within(state_dir, git_root):
        raise AuditError(f"state directory is inside the git work tree: {state_dir}")
    return state_dir


def raise_walk_error(error):
    raise error


def snapshot_kb(kb):
    if os.path.islink(kb) or not os.path.isdir(kb):
        return {"files": {}, "papers": []}

    files = {}
    for root, directories, names in os.walk(
        kb, topdown=True, onerror=raise_walk_error, followlinks=False
    ):
        directories.sort()
        names.sort()
        kept_directories = []
        for name in directories:
            path = os.path.join(root, name)
            if os.path.islink(path):
                relative = os.path.relpath(path, kb)
                files[relative] = {
                    "type": "symlink",
                    "target": os.readlink(path),
                }
            else:
                kept_directories.append(name)
        directories[:] = kept_directories
        for name in names:
            path = os.path.join(root, name)
            relative = os.path.relpath(path, kb)
            if os.path.islink(path):
                files[relative] = {
                    "type": "symlink",
                    "target": os.readlink(path),
                }
            elif os.path.isfile(path):
                files[relative] = {
                    "type": "file",
                    "size": os.path.getsize(path),
                    "sha256": sha256_file(path),
                }
            else:
                raise AuditError(f"unsupported knowledge-base entry: {path}")

    papers = []
    papers_dir = os.path.join(kb, "papers")
    if os.path.isdir(papers_dir) and not os.path.islink(papers_dir):
        with os.scandir(papers_dir) as entries:
            papers = sorted(
                entry.name
                for entry in entries
                if entry.is_dir(follow_symlinks=False)
            )
    return {"files": dict(sorted(files.items())), "papers": papers}


def run_git(root, arguments):
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["LC_ALL"] = "C"
    return subprocess.run(
        ["git", "-C", root, *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )


def discover_git_root(project):
    try:
        result = run_git(project, ["rev-parse", "--show-toplevel"])
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return os.path.realpath(os.fsdecode(result.stdout).strip())


def git_value(root, arguments):
    result = run_git(root, arguments)
    if result.returncode != 0:
        raise AuditError(
            f"git {' '.join(arguments)} failed: "
            f"{result.stderr.decode('utf-8', 'replace').strip() or 'unknown error'}"
        )
    return result.stdout


def read_head(root):
    result = run_git(root, ["rev-parse", "--verify", "HEAD"])
    if result.returncode == 0:
        return result.stdout.decode("ascii", "replace").strip()
    symbolic = run_git(root, ["symbolic-ref", "-q", "HEAD"])
    if symbolic.returncode == 0:
        return "unborn"
    raise AuditError("cannot read repository HEAD state")


def snapshot_untracked(root, exclusion):
    raw = git_value(
        root,
        ["ls-files", "--others", "--exclude-standard", "-z", "--", ".", exclusion],
    )
    entries = {}
    for encoded_path in raw.split(b"\0"):
        if not encoded_path:
            continue
        relative = os.fsdecode(encoded_path)
        path = os.path.join(root, relative)
        if os.path.islink(path):
            entries[relative] = {
                "type": "symlink",
                "target": os.readlink(path),
            }
        elif os.path.isfile(path):
            entries[relative] = {
                "type": "file",
                "size": os.path.getsize(path),
                "sha256": sha256_file(path),
            }
        else:
            raise AuditError(f"cannot snapshot untracked file: {path}")
    return dict(sorted(entries.items()))


def unavailable_git(reason):
    return {"available": False, "error": str(reason)}


def snapshot_git(project, kb, expected_root=None):
    try:
        if expected_root is None:
            discovered = run_git(project, ["rev-parse", "--show-toplevel"])
            if discovered.returncode != 0:
                return unavailable_git("project is not inside a git work tree")
            root = os.path.realpath(os.fsdecode(discovered.stdout).strip())
        else:
            root = expected_root
            discovered = run_git(project, ["rev-parse", "--show-toplevel"])
            if discovered.returncode != 0:
                return unavailable_git("git work tree is no longer available")
            current_root = os.path.realpath(os.fsdecode(discovered.stdout).strip())
            if current_root != root:
                return unavailable_git("git work-tree root changed")

        relative_kb = os.path.relpath(kb, root)
        if relative_kb == os.pardir or relative_kb.startswith(os.pardir + os.sep):
            return unavailable_git("knowledge base is outside the git work tree")
        relative_kb = relative_kb.replace(os.sep, "/")
        exclusion = f":(top,exclude,literal){relative_kb}"

        head = read_head(root)
        branch = git_value(root, ["branch", "--show-current"]).decode(
            "utf-8", "replace"
        ).strip()
        staged = git_value(root, ["diff", "--cached", "--binary"])
        outside_status = git_value(
            root,
            [
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                ".",
                exclusion,
            ],
        )
        outside_diff = git_value(
            root, ["diff", "--binary", "--", ".", exclusion]
        )
        outside_untracked = snapshot_untracked(root, exclusion)
        return {
            "available": True,
            "root": root,
            "head": head,
            "branch": branch,
            "staged_diff_sha256": sha256_bytes(staged),
            "outside_status": outside_status.decode("utf-8", "replace"),
            "outside_status_sha256": sha256_bytes(outside_status),
            "outside_diff_sha256": sha256_bytes(outside_diff),
            "outside_untracked": outside_untracked,
        }
    except (AuditError, OSError) as error:
        return unavailable_git(error)


def build_snapshot(project, kb, expected_git_root=None):
    kb_snapshot = snapshot_kb(kb)
    return {
        "version": 1,
        "project": project,
        "kb": kb,
        "kb_root_symlink": os.path.islink(kb),
        "files": kb_snapshot["files"],
        "papers": kb_snapshot["papers"],
        "git": snapshot_git(project, kb, expected_git_root),
    }


def write_json(path, value):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = f"{path}.tmp.{os.getpid()}"
    try:
        with open(temporary, "w", encoding="utf-8") as destination:
            json.dump(value, destination, indent=2, sort_keys=True)
            destination.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def command_init(args):
    project = resolve_project(args.project)
    kb = kb_path(project)
    script_path = os.path.realpath(__file__)
    template = os.path.realpath(
        os.path.join(os.path.dirname(script_path), "..", "assets", "kb-template")
    )
    if not os.path.isdir(template):
        raise AuditError(f"knowledge-base template is missing: {template}")

    try:
        os.mkdir(kb)
    except FileExistsError:
        if os.path.islink(kb):
            raise AuditError(
                f"knowledge-base path is a symlink; refusing to initialize: {kb}"
            )
        raise AuditError(f"knowledge base already exists; refusing to overwrite: {kb}")
    created = os.stat(kb, follow_symlinks=False)

    try:
        shutil.copytree(template, kb, symlinks=True, dirs_exist_ok=True)
        os.replace(os.path.join(kb, "gitignore"), os.path.join(kb, ".gitignore"))
    except Exception:
        try:
            current = os.stat(kb, follow_symlinks=False)
            same_directory = (current.st_dev, current.st_ino) == (
                created.st_dev,
                created.st_ino,
            )
        except OSError:
            same_directory = False
        if same_directory and os.path.isdir(kb) and not os.path.islink(kb):
            shutil.rmtree(kb)
        raise
    print(f"INITIALIZED={kb}")


def command_before(args):
    project = resolve_project(args.project)
    kb = validate_kb_for_before(project)
    state_dir = resolve_state_dir(args.state_dir, project, discover_git_root(project))
    os.makedirs(state_dir, exist_ok=True)
    snapshot = build_snapshot(project, kb)
    destination = os.path.join(state_dir, STATE_FILE)
    write_json(destination, snapshot)
    print(f"SNAPSHOT={destination}")
    if snapshot["git"].get("available"):
        print("GIT=available")
    else:
        print(f"GIT=unavailable:{flatten(snapshot['git'].get('error', 'unknown'))}")


def load_before(state_dir):
    path = os.path.join(state_dir, STATE_FILE)
    if not os.path.isfile(path):
        raise AuditError(f"before snapshot is missing: {path}")
    try:
        with open(path, "r", encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise AuditError(f"cannot read before snapshot: {error}") from error
    required = {"version", "project", "kb", "files", "papers", "git"}
    if (
        not isinstance(value, dict)
        or not required.issubset(value)
        or value["version"] != 1
        or not isinstance(value["files"], dict)
        or not isinstance(value["papers"], list)
        or not isinstance(value["git"], dict)
    ):
        raise AuditError(f"before snapshot is malformed: {path}")
    return value


def compare_git(before, after):
    if not before.get("available") or not after.get("available"):
        return "unknown"
    if after.get("head") != before.get("head"):
        return "head-moved"
    if after.get("branch") != before.get("branch"):
        return "branch-changed"
    if after.get("staged_diff_sha256") != before.get("staged_diff_sha256"):
        return "staged-changes"
    outside_keys = (
        "outside_status_sha256",
        "outside_diff_sha256",
        "outside_untracked",
    )
    if any(after.get(key) != before.get(key) for key in outside_keys):
        return "outside-kb-writes"
    return "none"


def compare_snapshots(before, after):
    before_files = before["files"]
    after_files = after["files"]
    changed = sum(
        1
        for path, metadata in after_files.items()
        if path not in before_files or before_files[path] != metadata
    )
    removed = sum(1 for path in before_files if path not in after_files)
    before_papers = set(before["papers"])
    after_papers = set(after["papers"])
    violation = compare_git(before["git"], after["git"])
    if after["kb_root_symlink"]:
        violation = "outside-kb-writes"
    return {
        "PAPERS_ADDED": len(after_papers - before_papers),
        "PAPERS_REMOVED": len(before_papers - after_papers),
        "KB_FILES_CHANGED": changed,
        "KB_FILES_REMOVED": removed,
        "KB_CHANGED": int(before_files != after_files),
        "POLICY_VIOLATION": violation,
    }


def command_after(args):
    project = resolve_project(args.project)
    state_dir = resolve_state_dir(args.state_dir, project, discover_git_root(project))
    json_file = None
    if args.json_file:
        json_file = os.path.realpath(args.json_file)
        if is_within(json_file, project):
            raise AuditError(f"JSON destination is inside the project: {json_file}")
        if is_within(json_file, state_dir):
            raise AuditError(f"JSON destination is inside the state directory: {json_file}")
    before = load_before(state_dir)
    if before["project"] != project or before["kb"] != kb_path(project):
        raise AuditError("before snapshot belongs to a different project")
    expected_root = before["git"].get("root") if before["git"].get("available") else None
    after = build_snapshot(project, kb_path(project), expected_root)
    comparison = compare_snapshots(before, after)
    if json_file:
        write_json(
            json_file,
            {"before": before, "after": after, "comparison": comparison},
        )
    for key in (
        "PAPERS_ADDED",
        "PAPERS_REMOVED",
        "KB_FILES_CHANGED",
        "KB_FILES_REMOVED",
        "KB_CHANGED",
        "POLICY_VIOLATION",
    ):
        print(f"{key}={comparison[key]}")


def make_parser():
    parser = Parser(description="Verify changes to a project literature knowledge base")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=Parser)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("project")
    init_parser.set_defaults(handler=command_init)

    before_parser = subparsers.add_parser("before")
    before_parser.add_argument("project")
    before_parser.add_argument("state_dir")
    before_parser.set_defaults(handler=command_before)

    after_parser = subparsers.add_parser("after")
    after_parser.add_argument("project")
    after_parser.add_argument("state_dir")
    after_parser.add_argument("--json", dest="json_file")
    after_parser.set_defaults(handler=command_after)
    return parser


def main():
    try:
        args = make_parser().parse_args()
        args.handler(args)
        return 0
    except Exception as error:
        return fail(error)


if __name__ == "__main__":
    sys.exit(main())
