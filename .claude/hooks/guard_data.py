"""Decul data guard: a PreToolUse hook that keeps the match data away from Claude.

The competition terms forbid giving the match data, or any extract of it, to a hosted LLM without
written authorisation (OVERVIEW.md, "Use of Large Language Models", and the terms accepted at
enrolment). Whatever a tool call reads lands in the conversation, so this hook refuses -- before it
runs -- every call that would open the data, open something computed from it, or run code that
reads it.

    exit 0  allow the call
    exit 2  block it; stderr is shown to Claude as the reason

It reads the *text* of a call only. A new script that opens the data without naming it is not
caught here; CLAUDE.md's rules cover that case, and the Bash sandbox would close it at OS level
(CLAUDE.md, "Enforcement"). Registered in .claude/settings.json with onFailure "block", so a crash
in this file blocks the call instead of letting it through.

Tests: python3 .claude/hooks/test_guard_data.py
"""

import fnmatch
import json
import os
import re
import shlex
import sys

# Params
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR")
                           or os.path.dirname(os.path.dirname(HERE)))

# Where the match data may live: the starter's default, our recommended home for it, and whatever
# MTAH_DATA_DIR points at (games.py reads the same variable). Caches computed from the data go
# under these too, so they inherit the protection.
PROTECTED_ROOTS = [os.path.realpath(p) for p in (
    os.path.join(PROJECT, "data"),
    os.path.expanduser("~/mtah-data"),
    os.environ.get("MTAH_DATA_DIR") or "",
) if p]

# Files outside those roots that hold output computed from the data, relative to the project.
# Decul's own submissions are frame-level labels from the data; scratch outputs in experiments/
# may be anything. The organisers' baseline_*.csv are public and stay readable.
DERIVED_PATTERNS = ["evaluation/results/[Dd]ecul*.csv"] + [
    "experiments/*" + suffix for suffix in (
        ".csv", ".npz", ".npy", ".parquet", ".pkl", ".pickle", ".png", ".jpg", ".jpeg", ".svg",
        ".ipynb", ".json", ".txt", ".xml", ".log")]

# data/README.md ships in the organisers' public repository; it describes the folder, not the data.
ALLOWED_FILES = {os.path.join(PROJECT, "data", "README.md"),
                 os.path.join(PROJECT, "experiments", "README.md")}

FILE_TOOLS = ("Read", "Edit", "MultiEdit", "Write", "NotebookEdit")
SEARCH_TOOLS = ("Grep", "Glob")

# Grep over a folder that contains the data is only allowed with a filter that cannot match it.
DATA_SUFFIXES = (".txt", ".xml", ".csv", ".mp4", ".npz", ".npy", ".json")

# A shell started on a string runs that string as a command: check it as one too.
NESTED_SHELL = re.compile(r"""(?:\b(?:ba|z)?sh\s+-\w*c|\beval)\s+(['"])(.*?)\1""", re.S)

# Read-only git commands that print paths, never file contents. The paths are public (DATA.md).
GIT_PATHS_ONLY = re.compile(r"^git\s+(ls-files|check-ignore|status)\b")
GIT_UNTRACKED_READ = re.compile(r"^git\s+(grep|diff)\b.*(--no-index|--untracked)")

# Exclusions that keep a recursive search out of data/: harmless, so stripped before checking.
EXCLUSIONS = re.compile(
    r"""--exclude-dir[= ]["']?(\./)?data/?["']?|(--glob|-g)[= ]["']?!(\./)?data[/*]*["']?""")

# A path into the data, however it is spelled.
DATA_PATH = re.compile(
    r"(?<![\w.$/-])(\./)?data/|mtah-data|MTAH_DATA_DIR|BAR-ATH_(tactical|broadcast)")

# Commands that list, print, copy or parse files.
READERS = (r"cd|ls|find|du|tree|cat|tac|head|tail|less|more|nl|rg|grep|egrep|fgrep|cp|mv|tar|zip"
           r"|rsync|stat|file|wc|xxd|od|hexdump|strings|sed|awk|sort|uniq|cut|paste|column|jq"
           r"|diff|cmp|open|base64")
READER = re.compile(r"^(\S*/)?(%s)\b" % READERS)
BARE_DATA = re.compile(r"(?<![\w.$/-])(\./)?data(?![\w.-])")

# Running code: anything after one of these executes.
EXECUTOR = re.compile(
    r"^(\w+=\S*\s+)*(\S*/)?(python3?(\.\d+)?|uv|uvx|bash|sh|zsh|source|\.|ipython|jupyter|papermill)\b"
    r"|^(\./)?(make_submission\.py|experiments/\S+\.sh)\b")
# ...and code that reads the data internally, so running it prints whatever it prints about it.
DATA_READERS = re.compile(
    r"make_submission|starter[/.](baseline|load_atd|load_smart_tagging|load_homography)\b"
    r"|experiments/\S*\.sh|run_all\.sh|final_checks\.sh"   # every experiments/ script is a data runner
    r"|\bjupyter\b|nbconvert|papermill|\.ipynb\b|solution[/.](atd|features|tagging)\b"
    r"|asset_paths|\brequire\(")

# Recursive readers: grep -r ignores .gitignore and would walk straight into data/.
RECURSIVE_GREP = re.compile(r"^(\S*/)?[ef]?grep\b.*(\s-\w*[rR]\w*\b|--recursive|--dereference-recursive)")
UNIGNORED_SEARCH = re.compile(r"^(\S*/)?(rg|ag)\b.*(\s-u+\b|--no-ignore|--unrestricted)")
FIND_EXEC = re.compile(r"^(\S*/)?find\b.*\s-(exec|execdir|ok|okdir)\b")
XARGS_READ = re.compile(r"^(\S*/)?xargs\b.*\b(cat|head|tail|less|more|strings|od|xxd|grep|python3?)\b")

MESSAGE = (
    "Blocked by the Decul data guard: {reason}.\n"
    "The match data must not reach a hosted LLM (CLAUDE.md, 'Hard rules'). Do not work around this.\n"
    "Ask the user to run it in their own terminal and paste only the output of\n"
    "evaluation/run_evaluation.py or evaluation/validate_submission.py.\n")


def resolve(path, cwd):
    full = os.path.expanduser(path)
    if not os.path.isabs(full):
        full = os.path.join(cwd, full)
    return os.path.realpath(full)


def is_protected(path, cwd):
    """True if `path` is match data or output computed from it, and not an allowed public file."""
    full = resolve(path, cwd)
    if full in ALLOWED_FILES:
        return False
    if any(full == root or full.startswith(root + os.sep) for root in PROTECTED_ROOTS):
        return True
    if full.startswith(PROJECT + os.sep):
        relative = os.path.relpath(full, PROJECT).replace(os.sep, "/")
        # experiments/ is scratch at any depth, so match its files by suffix wherever they sit.
        flattened = re.sub(r"^experiments/.*/", "experiments/", relative)
        return any(fnmatch.fnmatch(flattened, pattern) for pattern in DERIVED_PATTERNS)
    return False


def contains_data(path, cwd):
    """True if searching `path` recursively would reach a protected root."""
    full = resolve(path, cwd)
    return any(root == full or root.startswith(full + os.sep) for root in PROTECTED_ROOTS)


def check_file(tool_input, cwd):
    for key in ("file_path", "notebook_path"):
        path = tool_input.get(key)
        if path and is_protected(path, cwd):
            return "{} is match data or output computed from it ({})".format(key, path)
    return None


def check_search(tool, tool_input, cwd):
    path = tool_input.get("path") or cwd
    if is_protected(path, cwd):
        return "{} searches inside the match data ({})".format(tool, path)
    for key in ("glob", "pattern"):
        value = tool_input.get(key) or ""
        if (tool == "Glob" or key == "glob") and (DATA_PATH.search(value)
                                                 or value.split("/")[0] == "data"):
            return "{} {} points into the match data ({})".format(tool, key, value)
    if tool == "Grep" and contains_data(path, cwd):
        file_filter = tool_input.get("glob") or tool_input.get("type") or ""
        if not file_filter or file_filter in ("*", "**", "**/*") \
                or any(file_filter.endswith(suffix) for suffix in DATA_SUFFIXES):
            return ("Grep over {} would reach the match data; search a subfolder or add a "
                    "glob/type filter such as '*.py'".format(path))
    return None


def split_segments(command):
    """Split on |, ||, &&, ; and newlines -- but not inside quotes.

    A '|' inside a quoted regex is an alternation, not a pipe; splitting there once made
    "grep -E '...|make_submission.py$'" look like a command that runs make_submission.py.
    """
    segments, current, quote, index = [], [], None, 0
    while index < len(command):
        char = command[index]
        if quote:
            current.append(char)
            if char == "\\" and quote == '"' and index + 1 < len(command):
                current.append(command[index + 1])
                index += 1
            elif char == quote:
                quote = None
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char == "\\" and index + 1 < len(command):
            current.append(char + command[index + 1])
            index += 1
        elif command.startswith(("&&", "||"), index):
            segments.append("".join(current))
            current = []
            index += 1
        elif char in "|;\n":
            segments.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    segments.append("".join(current))
    return segments


def tokens(segment):
    try:
        return shlex.split(segment)
    except ValueError:  # unbalanced quotes: fall back to whitespace, still good enough to match
        return segment.split()


def grep_paths(segment):
    """The folders a grep command searches: its operands after the pattern."""
    paths, have_pattern, skip = [], False, False
    for token in tokens(segment)[1:]:
        if skip:
            skip = False
        elif token in ("-e", "-f", "--regexp", "--file"):
            have_pattern, skip = True, True
        elif token.startswith(("--regexp=", "--file=")):
            have_pattern = True
        elif token in ("--include", "--exclude", "--exclude-dir", "-m", "--max-count",
                       "-A", "-B", "-C", "--after-context", "--before-context", "--context"):
            skip = True
        elif token.startswith("-"):
            continue
        elif not have_pattern:
            have_pattern = True
        else:
            paths.append(token)
    return paths


def check_segment(segment, cwd):
    excluded = bool(EXCLUSIONS.search(segment))
    segment = EXCLUSIONS.sub(" ", segment).strip()
    if GIT_PATHS_ONLY.match(segment):
        return None
    if segment.startswith("git"):
        if DATA_PATH.search(segment) or GIT_UNTRACKED_READ.match(segment):
            return "git would read files outside version control, such as the data"
        return None  # git only sees tracked files, and the data is never tracked

    if DATA_PATH.search(segment):
        return "the command names the match data"
    reader = READER.match(segment)
    if reader and BARE_DATA.search(segment[reader.end():]):
        return "the command lists, reads or copies the data folder"
    if reader and any(is_protected(token, cwd) for token in tokens(segment)[1:]
                      if not token.startswith("-")):
        return "the command reads output computed from the match data"
    if EXECUTOR.match(segment) and DATA_READERS.search(segment):
        return "the command runs code that reads the match data"
    if RECURSIVE_GREP.match(segment) and not excluded:
        # grep -r ignores .gitignore; with no folder it searches the current one.
        paths = grep_paths(segment) or ["."]
        if any(contains_data(path, cwd) or is_protected(path, cwd) for path in paths):
            return ("grep -r would walk into the data folder; search a subfolder, use git grep, "
                    "or add --exclude-dir=data")
    for pattern, reason in (
            (UNIGNORED_SEARCH, "an unrestricted search would read the data folder"),
            (FIND_EXEC, "find -exec could read the data folder"),
            (XARGS_READ, "xargs would read files that may be the data")):
        if pattern.match(segment):
            return reason
    return None


def check_bash(command, cwd):
    for root in PROTECTED_ROOTS:
        if root in command or root.replace(" ", "\\ ") in command:
            return "the command names the match data folder"
    for nested in NESTED_SHELL.finditer(command):
        reason = check_bash(nested.group(2), cwd)
        if reason:
            return reason
    for segment in split_segments(command):
        segment = segment.strip().lstrip("({ ").strip()
        reason = segment and check_segment(segment, cwd)
        if reason:
            return "{} ({!r})".format(reason, segment[:120])
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        sys.stderr.write(MESSAGE.format(reason="the hook could not parse its input"))
        return 2

    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd") or PROJECT

    reason = None
    if tool in FILE_TOOLS:
        reason = check_file(tool_input, cwd)
    elif tool in SEARCH_TOOLS:
        reason = check_search(tool, tool_input, cwd)
    elif tool == "Bash":
        reason = check_bash(tool_input.get("command") or "", cwd)

    if reason:
        sys.stderr.write(MESSAGE.format(reason=reason))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
