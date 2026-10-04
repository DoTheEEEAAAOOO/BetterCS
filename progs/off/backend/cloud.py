import base64
import http.client
import ipaddress
import json
import re
import secrets
import socket
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from flask import Blueprint, Response, jsonify, request
from backend.session_store import load_saved_sessions, save_sessions


cloud_api = Blueprint("cloud_api", __name__)
sessions = load_saved_sessions()
GITHUB_API = "https://api.github.com"
TREE_FILE_PATH = ".bettercs/tree.json"
SESSION_COOKIE = "bettercs_session"
SESSION_MAX_AGE = 30 * 24 * 60 * 60
MAX_BROWSER_PAGE_BYTES = 2 * 1024 * 1024
MAX_BROWSER_REDIRECTS = 5
BETTER_FILES_SOURCE = (Path(__file__).resolve().parent / "default_apps" / "BetterFiles.js").read_text(encoding="utf-8")
BETTERSURF_APP_SOURCE = (Path(__file__).resolve().parent / "default_apps" / "BetterSurf.js").read_text(encoding="utf-8")
LEGACY_FILES_APP_MARKER = "The Files app is ready for your BetterCS repository."
VERSIONED_FILES_APP_MARKER = "BETTERCS_FILES_APP_VERSION = 2"
DEFAULT_APP_SOURCES = {
    "BetterFiles.js": BETTER_FILES_SOURCE,
    "BetterSurf.js": BETTERSURF_APP_SOURCE,
        "Placeholder.js": '''export default function Placeholder(van) {
    const {div, h2, p} = van.tags
    return div({class: "bettercs-app bettercs-placeholder"},
        h2("Welcome to BetterCS"),
        p("Choose an app from the bottom bar to get started."),
    )
}
''',
}


def github_request(token, path, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    github_request = Request(
        f"{GITHUB_API}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "BetterCS",
        },
    )

    try:
        with urlopen(github_request, timeout=20) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}
    except HTTPError as error:
        body = error.read()
        try:
            details = json.loads(body) if body else {}
        except json.JSONDecodeError:
            details = {}
        return error.code, details
    except (URLError, TimeoutError):
        return None, {}


def validate_browser_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None, "Only public HTTP and HTTPS websites are supported."
        if parsed.username or parsed.password:
            return None, "URLs containing embedded credentials are not allowed."

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port != (443 if parsed.scheme == "https" else 80):
            return None, "Only standard HTTP and HTTPS ports are supported."

        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".onion")):
            return None, "Local and private network addresses are not allowed."

        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = [
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ]
        if not addresses or any(not address.is_global for address in addresses):
            return None, "Local and private network addresses are not allowed."

        path = parsed.path or "/"
        netloc = f"[{host}]" if ":" in host else host
        if parsed.port:
            netloc = f"{netloc}:{port}"
        normalized_url = urlunsplit((parsed.scheme, netloc, path, parsed.query, ""))
        return (normalized_url, host, port, addresses[0]), None
    except (ValueError, UnicodeError, OSError, socket.gaierror):
        return None, "That website address could not be resolved."


def fetch_public_html(url):
    class PinnedHTTPConnection(http.client.HTTPConnection):
        def __init__(self, host, port, address):
            super().__init__(host, port, timeout=10)
            self.address = address

        def connect(self):
            self.sock = socket.create_connection((self.address, self.port), self.timeout)

    class PinnedHTTPSConnection(http.client.HTTPSConnection):
        def __init__(self, host, port, address):
            super().__init__(host, port, timeout=10, context=ssl.create_default_context())
            self.address = address

        def connect(self):
            raw_socket = socket.create_connection((self.address, self.port), self.timeout)
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)

    current_url = url
    for redirect_count in range(MAX_BROWSER_REDIRECTS + 1):
        validated, error = validate_browser_url(current_url)
        if error:
            return None, None, error
        normalized_url, host, port, address = validated
        parsed = urlsplit(normalized_url)
        request_path = urlunsplit(("", "", parsed.path, parsed.query, ""))
        connection_type = PinnedHTTPSConnection if parsed.scheme == "https" else PinnedHTTPConnection
        connection = connection_type(host, port, str(address))

        try:
            connection.request(
                "GET",
                request_path,
                headers={
                    "Host": parsed.netloc,
                    "User-Agent": "BetterCS-BetterSurf/1.0",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location or redirect_count == MAX_BROWSER_REDIRECTS:
                    return None, None, "The website redirected too many times."
                current_url = urljoin(normalized_url, location)
                continue
            if response.status != 200:
                return None, None, f"The website returned HTTP {response.status}."

            content_type = response.getheader("Content-Type", "")
            if "text/html" not in content_type.lower() and "application/xhtml+xml" not in content_type.lower():
                return None, None, "The address did not return an HTML page."

            page_bytes = response.read(MAX_BROWSER_PAGE_BYTES + 1)
            if len(page_bytes) > MAX_BROWSER_PAGE_BYTES:
                return None, None, "The HTML page is larger than BetterSurf's 2 MB limit."
            charset_match = re.search(r"charset=([\w.-]+)", content_type, re.IGNORECASE)
            charset = charset_match.group(1) if charset_match else "utf-8"
            try:
                page_html = page_bytes.decode(charset)
            except (LookupError, UnicodeDecodeError):
                page_html = page_bytes.decode("utf-8", errors="replace")
            return page_html, normalized_url, None
        except (OSError, http.client.HTTPException, ssl.SSLError):
            return None, None, "BetterSurf could not load that website."
        finally:
            connection.close()

    return None, None, "The website redirected too many times."


def current_session():
    expired_session_ids = []
    for session_id in request.cookies.getlist(SESSION_COOKIE):
        session = sessions.get(session_id)
        if session is None:
            continue
        if session.get("expiresAt", 0) <= time.time():
            expired_session_ids.append(session_id)
            continue
        if expired_session_ids:
            for expired_session_id in expired_session_ids:
                sessions.pop(expired_session_id, None)
            save_sessions(sessions)
        return session

    if expired_session_ids:
        for expired_session_id in expired_session_ids:
            sessions.pop(expired_session_id, None)
        save_sessions(sessions)
    return None


def require_session():
    session = current_session()
    if session is None:
        return None, (jsonify({"ok": False, "message": "Sign in to BetterCS first."}), 401)
    return session, None


def build_tree(entries, repository, branch):
    root = {"type": "directory", "children": {}}

    for entry in entries:
        path_parts = entry.get("path", "").split("/")
        if not path_parts or not path_parts[0]:
            continue

        current = root
        for directory in path_parts[:-1]:
            children = current["children"]
            current = children.setdefault(
                directory,
                {"type": "directory", "children": {}},
            )

        name = path_parts[-1]
        if entry.get("type") == "tree":
            current["children"].setdefault(
                name,
                {"type": "directory", "children": {}},
            )
        else:
            current["children"][name] = {
                "type": entry.get("type", "file"),
                "path": entry.get("path"),
                "sha": entry.get("sha"),
                "size": entry.get("size"),
                "mode": entry.get("mode", "100644"),
            }

    return {
        "schemaVersion": 1,
        "repository": repository,
        "branch": branch,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "root": root,
    }


class TreeOperationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalize_tree_path(value):
    if not isinstance(value, str):
        raise TreeOperationError("A file or folder path is required.")

    path = value.strip()
    parts = path.split("/")
    if (
        not path
        or len(path) > 1024
        or path.startswith("/")
        or "\\" in path
        or any(part in ("", ".", "..") for part in parts)
        or parts[0] == ".bettercs"
    ):
        raise TreeOperationError("Use a repository-relative path without empty, dot, or parent segments.")
    return "/".join(parts)


def get_tree_node(tree, path):
    node = tree["root"]
    for part in path.split("/"):
        if node.get("type") != "directory":
            return None
        node = node["children"].get(part)
        if node is None:
            return None
    return node


def get_tree_parent(tree, path):
    parts = path.split("/")
    parent_path = "/".join(parts[:-1])
    parent = tree["root"] if not parent_path else get_tree_node(tree, parent_path)
    if parent is None or parent.get("type") != "directory":
        raise TreeOperationError("Create the parent folder before adding items.", 404)
    return parent, parts[-1]


def iter_tree_files(node, parent_path=""):
    for name, child in node.get("children", {}).items():
        path = f"{parent_path}/{name}" if parent_path else name
        if child.get("type") == "directory":
            yield from iter_tree_files(child, path)
        else:
            yield path, child


def update_file_paths(node, parent_path=""):
    for name, child in node.get("children", {}).items():
        path = f"{parent_path}/{name}" if parent_path else name
        if child.get("type") == "directory":
            update_file_paths(child, path)
        else:
            child["path"] = path


def queue_file_deletion(session, path):
    if path in session["base_files"]:
        session["pending"][path] = None
    else:
        session["pending"].pop(path, None)


def apply_tree_operation(session, payload):
    tree = session["tree"]
    pending = session["pending"]
    operation = str(payload.get("operation", ""))
    path = normalize_tree_path(payload.get("path"))
    node = get_tree_node(tree, path)

    if operation in ("add-file", "edit-file"):
        content = payload.get("content")
        if not isinstance(content, str):
            raise TreeOperationError("File content must be a string.")

        if operation == "add-file":
            if node is not None:
                raise TreeOperationError("That path already exists.", 409)
        elif node is None or node.get("type") == "directory":
            raise TreeOperationError("Choose an existing file path to edit.", 404)

        parent, name = get_tree_parent(tree, path)
        existing = parent["children"].get(name)
        mode = existing.get("mode", "100644") if existing else "100644"
        parent["children"][name] = {
            "type": "blob",
            "path": path,
            "sha": existing.get("sha") if existing else None,
            "size": len(content.encode("utf-8")),
            "mode": mode,
        }
        pending[path] = {"content": content, "mode": mode}
    elif operation == "remove-file":
        if node is None or node.get("type") == "directory":
            raise TreeOperationError("Choose an existing file path to remove.", 404)
        parent, name = get_tree_parent(tree, path)
        del parent["children"][name]
        queue_file_deletion(session, path)
    elif operation == "make-folder":
        if node is not None:
            raise TreeOperationError("That path already exists.", 409)
        parent, name = get_tree_parent(tree, path)
        parent["children"][name] = {
            "type": "directory",
            "children": {
                ".gitkeep": {
                    "type": "blob",
                    "path": f"{path}/.gitkeep",
                    "sha": None,
                    "size": 0,
                    "mode": "100644",
                },
            },
        }
        pending[f"{path}/.gitkeep"] = {"content": "", "mode": "100644"}
    elif operation == "remove-folder":
        if node is None or node.get("type") != "directory":
            raise TreeOperationError("Choose an existing folder path to remove.", 404)
        parent, name = get_tree_parent(tree, path)
        for file_path, _ in list(iter_tree_files(node, path)):
            queue_file_deletion(session, file_path)
        del parent["children"][name]
    elif operation in ("rename-file", "rename-folder"):
        destination = normalize_tree_path(payload.get("newPath"))
        if operation == "rename-file" and (node is None or node.get("type") == "directory"):
            raise TreeOperationError("Choose an existing file path to rename.", 404)
        if operation == "rename-folder" and (node is None or node.get("type") != "directory"):
            raise TreeOperationError("Choose an existing folder path to rename.", 404)
        if destination == path or destination.startswith(f"{path}/"):
            raise TreeOperationError("A folder cannot be moved inside itself.")
        if get_tree_node(tree, destination) is not None:
            raise TreeOperationError("The destination path already exists.", 409)

        source_parent, source_name = get_tree_parent(tree, path)
        destination_parent, destination_name = get_tree_parent(tree, destination)
        moved_node = source_parent["children"].pop(source_name)
        destination_parent["children"][destination_name] = moved_node
        if moved_node.get("type") == "directory":
            update_file_paths(moved_node, destination)
        else:
            moved_node["path"] = destination

        moved_files = list(iter_tree_files(moved_node, destination)) if moved_node.get("type") == "directory" else [(destination, moved_node)]
        original_files = list(iter_tree_files(moved_node, destination)) if moved_node.get("type") == "directory" else [(path, moved_node)]
        if moved_node.get("type") == "directory":
            original_files = [
                (f"{path}{new_file_path[len(destination):]}", file_node)
                for new_file_path, file_node in moved_files
            ]

        for old_file_path, file_node in original_files:
            relative_path = old_file_path[len(path):].lstrip("/")
            new_file_path = f"{destination}/{relative_path}" if relative_path else destination
            prior_pending = pending.pop(old_file_path, None)
            queue_file_deletion(session, old_file_path)
            if prior_pending is not None:
                pending[new_file_path] = prior_pending
            elif file_node.get("sha"):
                pending[new_file_path] = {
                    "sha": file_node["sha"],
                    "mode": file_node.get("mode", "100644"),
                    "type": file_node.get("type", "blob"),
                }

    else:
        raise TreeOperationError("Unknown tree operation.")

    tree["updatedAt"] = datetime.now(timezone.utc).isoformat()
    return tree


def export_tree(node):
    if node.get("type") == "directory":
        return {
            "type": "directory",
            "children": {name: export_tree(child) for name, child in node.get("children", {}).items()},
        }
    return {
        "type": node.get("type", "blob"),
        "path": node.get("path"),
        "size": node.get("size"),
    }


def serialized_tree_for_storage(tree):
    return {
        "schemaVersion": tree["schemaVersion"],
        "repository": tree["repository"],
        "branch": tree["branch"],
        "updatedAt": tree["updatedAt"],
        "root": export_tree(tree["root"]),
    }


def count_pending_changes(session):
    return len(session["pending"])


def restore_repository_tree(session):
    repository = session.get("repo")
    if not repository or "/" not in repository:
        return None, ("Link a GitHub repository first.", 409)

    owner, name = repository.split("/", 1)
    repo_path = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    repo_status, details = github_request(session["token"], repo_path)
    if repo_status is None:
        return None, ("Could not contact GitHub. Try again later.", 502)
    if repo_status != 200:
        return None, ("The saved GitHub repository is no longer accessible.", 403)

    branch = details.get("default_branch") or session.get("branch")
    if not branch:
        return None, ("The saved repository has no default branch.", 409)

    tree_status, tree_data = github_request(
        session["token"],
        f"{repo_path}/git/trees/{quote(branch, safe='')}?recursive=1",
    )
    if tree_status is None:
        return None, ("Could not contact GitHub. Try again later.", 502)
    if tree_status != 200:
        return None, ("Could not reload the repository file tree.", 502)
    if tree_data.get("truncated"):
        return None, ("This repository is too large to load as one file tree.", 413)

    entries = [
        entry for entry in tree_data.get("tree", [])
        if entry.get("path") != ".bettercs"
        and not entry.get("path", "").startswith(".bettercs/")
    ]
    session["tree"] = build_tree(entries, repository, branch)
    session["branch"] = branch
    session["base_files"] = {
        path: {
            "sha": node.get("sha"),
            "mode": node.get("mode", "100644"),
            "type": node.get("type", "blob"),
        }
        for path, node in iter_tree_files(session["tree"]["root"])
        if node.get("sha")
    }
    session["pending"] = {}
    return session["tree"], None


def initialize_empty_repository(session, repository, repo_path, branch, existing_entries=()):
    existing_entries = list(existing_entries)
    existing_app_names = {
        entry["path"].split("/", 1)[1]
        for entry in existing_entries
        if entry.get("path", "").startswith("Apps/")
        and entry["path"].count("/") == 1
        and entry["path"].endswith(".js")
    }
    app_entries = [
        {
            "path": f"Apps/{filename}",
            "mode": "100644",
            "type": "blob",
            "content": source,
        }
        for filename, source in DEFAULT_APP_SOURCES.items()
        if filename not in existing_app_names
    ]
    initial_tree = build_tree(
        [
            *existing_entries,
            *[{"path": entry["path"], "type": "blob", "mode": entry["mode"]} for entry in app_entries],
        ],
        repository,
        branch,
    )
    metadata = json.dumps(
        serialized_tree_for_storage(initial_tree),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    tree_entries = [*app_entries, {
        "path": TREE_FILE_PATH,
        "mode": "100644",
        "type": "blob",
        "content": metadata,
    }]

    ref_path = f"{repo_path}/git/ref/heads/{quote(branch, safe='')}"
    ref_status, ref = github_request(session["token"], ref_path)
    parent_sha = None
    tree_payload = {"tree": tree_entries}
    if ref_status == 200:
        parent_sha = ref.get("object", {}).get("sha")
        parent_status, parent_commit = github_request(
            session["token"],
            f"{repo_path}/git/commits/{quote(parent_sha or '', safe='')}",
        )
        if parent_status != 200:
            return None, ("Could not read the empty repository's current commit.", 502)
        tree_payload["base_tree"] = parent_commit.get("tree", {}).get("sha")
    elif ref_status != 404:
        return None, ("Could not inspect the repository branch before initializing it.", 502)

    tree_status, created_tree = github_request(
        session["token"],
        f"{repo_path}/git/trees",
        method="POST",
        payload=tree_payload,
    )
    if tree_status != 201:
        return None, ("GitHub could not create the initial Apps tree.", 502)

    commit_payload = {
        "message": "Initialize BetterCS apps",
        "tree": created_tree.get("sha"),
        "parents": [parent_sha] if parent_sha else [],
    }
    commit_status, commit = github_request(
        session["token"],
        f"{repo_path}/git/commits",
        method="POST",
        payload=commit_payload,
    )
    if commit_status != 201:
        return None, ("GitHub could not commit the initial Apps files.", 502)

    if parent_sha:
        ref_write_status, _ = github_request(
            session["token"],
            f"{repo_path}/git/refs/heads/{quote(branch, safe='')}",
            method="PATCH",
            payload={"sha": commit.get("sha"), "force": False},
        )
    else:
        ref_write_status, _ = github_request(
            session["token"],
            f"{repo_path}/git/refs",
            method="POST",
            payload={"ref": f"refs/heads/{branch}", "sha": commit.get("sha")},
        )
    if ref_write_status not in (200, 201):
        return None, ("GitHub could not publish the initial Apps branch.", 502)

    actual_entries = [
        entry for entry in created_tree.get("tree", [])
        if entry.get("path") != ".bettercs"
        and not entry.get("path", "").startswith(".bettercs/")
    ]
    session["repo"] = repository
    session["branch"] = branch
    session["tree"] = build_tree(actual_entries, repository, branch)
    session["base_files"] = {
        path: {
            "sha": node.get("sha"),
            "mode": node.get("mode", "100644"),
            "type": node.get("type", "blob"),
        }
        for path, node in iter_tree_files(session["tree"]["root"])
        if node.get("sha")
    }
    session["pending"] = {}
    save_sessions(sessions)
    return session["tree"], None


def ensure_default_apps(session, tree):
    apps_directory = get_tree_node(tree, "Apps")
    if apps_directory and apps_directory.get("type") == "directory":
        browser_node = apps_directory["children"].get("Browser.js")
        better_surf_node = apps_directory["children"].get("BetterSurf.js")
        if browser_node and browser_node.get("type") != "directory" and better_surf_node is None:
            old_path = "Apps/Browser.js"
            new_path = "Apps/BetterSurf.js"
            source, source_error = read_app_source(session, tree, "Browser")
            if not source_error:
                previous_pending = session["pending"].pop(old_path, None)
                del apps_directory["children"]["Browser.js"]
                renamed_node = {**browser_node, "path": new_path}
                apps_directory["children"]["BetterSurf.js"] = renamed_node
                queue_file_deletion(session, old_path)
                session["pending"][new_path] = previous_pending or {
                    "content": source,
                    "mode": browser_node.get("mode", "100644"),
                }

        files_node = apps_directory["children"].get("Files.js")
        if files_node and files_node.get("type") != "directory":
            old_path = "Apps/Files.js"
            new_path = "Apps/BetterFiles.js"
            better_files_node = apps_directory["children"].get("BetterFiles.js")
            source, source_error = read_app_source(session, tree, "Files")
            if not source_error:
                is_shipped_files_app = (
                    LEGACY_FILES_APP_MARKER in source
                    or VERSIONED_FILES_APP_MARKER in source
                )
                if better_files_node is None:
                    previous_pending = session["pending"].pop(old_path, None)
                    del apps_directory["children"]["Files.js"]
                    renamed_node = {**files_node, "path": new_path}
                    apps_directory["children"]["BetterFiles.js"] = renamed_node
                    queue_file_deletion(session, old_path)

                    if is_shipped_files_app:
                        session["pending"][new_path] = {
                            "content": BETTER_FILES_SOURCE,
                            "mode": files_node.get("mode", "100644"),
                        }
                        renamed_node["sha"] = files_node.get("sha")
                        renamed_node["size"] = len(BETTER_FILES_SOURCE.encode("utf-8"))
                    elif previous_pending is not None:
                        session["pending"][new_path] = previous_pending
                    elif files_node.get("sha"):
                        session["pending"][new_path] = {
                            "sha": files_node["sha"],
                            "mode": files_node.get("mode", "100644"),
                            "type": files_node.get("type", "blob"),
                        }
                    else:
                        session["pending"][new_path] = {
                            "content": source,
                            "mode": files_node.get("mode", "100644"),
                        }
                elif is_shipped_files_app:
                    del apps_directory["children"]["Files.js"]
                    queue_file_deletion(session, old_path)

    existing_names = set()
    if apps_directory and apps_directory.get("type") == "directory":
        existing_names = {
            name for name, node in apps_directory["children"].items()
            if node.get("type") != "directory" and name.endswith(".js")
        }

    missing_sources = {
        name: source
        for name, source in DEFAULT_APP_SOURCES.items()
        if name not in existing_names and f"Apps/{name}" not in session["pending"]
    }
    if not missing_sources:
        files_node = get_tree_node(tree, "Apps/BetterFiles.js")
        files_path = "Apps/BetterFiles.js"
        if (
            files_node
            and files_node.get("type") != "directory"
            and files_node.get("sha")
            and files_path not in session["pending"]
        ):
            current_source, source_error = read_app_source(session, tree, "BetterFiles")
            if not source_error and LEGACY_FILES_APP_MARKER in current_source:
                session["pending"][files_path] = {
                    "content": BETTER_FILES_SOURCE,
                    "mode": files_node.get("mode", "100644"),
                }
                files_node["size"] = len(BETTER_FILES_SOURCE.encode("utf-8"))
        return tree, None

    if session["pending"]:
        apps_directory = tree["root"]["children"].setdefault(
            "Apps",
            {"type": "directory", "children": {}},
        )
        for filename, source in missing_sources.items():
            path = f"Apps/{filename}"
            apps_directory["children"][filename] = {
                "type": "blob",
                "path": path,
                "sha": None,
                "size": len(source.encode("utf-8")),
                "mode": "100644",
            }
            session["pending"][path] = {"content": source, "mode": "100644"}
        return tree, None

    existing_entries = [
        {
            "path": path,
            "type": node.get("type", "blob"),
            "sha": node.get("sha"),
            "mode": node.get("mode", "100644"),
            "size": node.get("size"),
        }
        for path, node in iter_tree_files(tree["root"])
    ]
    owner, repo_name = session["repo"].split("/", 1)
    repo_path = f"/repos/{quote(owner, safe='')}/{quote(repo_name, safe='')}"
    return initialize_empty_repository(
        session,
        session["repo"],
        repo_path,
        tree["branch"],
        existing_entries=existing_entries,
    )


@cloud_api.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    token = str(payload.get("token", "")).strip()
    if not username or not token:
        return jsonify({"ok": False, "message": "Enter your GitHub username and token."}), 400

    status, user = github_request(token, "/user")
    if status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if status == 401:
        return jsonify({"ok": False, "message": "GitHub rejected that token."}), 401
    if status != 200:
        return jsonify({"ok": False, "message": "GitHub could not verify this login right now."}), 502
    if user.get("login", "").casefold() != username.casefold():
        return jsonify({"ok": False, "message": "That token belongs to a different GitHub username."}), 403

    session_id = secrets.token_urlsafe(32)
    sessions.clear()
    sessions[session_id] = {
        "token": token,
        "username": user["login"],
        "repo": None,
        "branch": None,
        "expiresAt": time.time() + SESSION_MAX_AGE,
        "tree": None,
        "base_files": {},
        "pending": {},
    }
    save_sessions(sessions)
    response = jsonify({"ok": True, "message": f"Signed in as {user['login']}.", "username": user["login"]})
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        secure=request.is_secure,
        samesite="Lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    response.delete_cookie(SESSION_COOKIE, path="/api", samesite="Lax")
    return response


@cloud_api.post("/api/logout")
def logout():
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        sessions.pop(session_id, None)
        save_sessions(sessions)

    response = jsonify({"ok": True, "message": "Signed out of BetterCS."})
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="Lax")
    response.delete_cookie(SESSION_COOKIE, path="/api", samesite="Lax")
    return response


@cloud_api.post("/api/repo")
def link_repository():
    session, error = require_session()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode", "existing")).strip().lower()

    if mode == "create":
        name = str(payload.get("repo", "bettercs-cloud")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            return jsonify({"ok": False, "message": "Use letters, numbers, dots, underscores, or hyphens for the repository name."}), 400

        status, details = github_request(
            session["token"],
            "/user/repos",
            method="POST",
            payload={
                "name": name,
                "private": True,
                "auto_init": False,
                "description": "BetterCS cloud storage",
            },
        )
        if status is None:
            return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
        if status == 422:
            return jsonify({"ok": False, "message": "That repository name is unavailable. Choose another name."}), 409
        if status != 201:
            return jsonify({"ok": False, "message": "GitHub could not create a private repository. Check that your token can create repositories."}), 403

        owner = details.get("owner", {}).get("login", session["username"])
        name = details.get("name", name)
    elif mode == "existing":
        repository = str(payload.get("repo", "")).strip()
        repository = re.sub(r"^https?://github\.com/", "", repository, flags=re.IGNORECASE)
        repository = repository.removesuffix(".git").strip("/")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            return jsonify({"ok": False, "message": "Use the format owner/repository or a GitHub repo URL."}), 400

        owner, name = repository.split("/", 1)
        repo_path = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
        status, details = github_request(session["token"], repo_path)
        if status is None:
            return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
        if status != 200:
            return jsonify({"ok": False, "message": "Repository not found or not accessible with this token."}), 403
    else:
        return jsonify({"ok": False, "message": "Choose an existing repository or create a private one."}), 400

    owner = details.get("owner", {}).get("login", owner)
    name = details.get("name", name)
    repo_path = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    normalized_repo = f"{owner}/{name}"
    if details.get("permissions", {}).get("push") is False:
        return jsonify({"ok": False, "message": "This GitHub token cannot write to that repository."}), 403

    branch = details.get("default_branch")
    if not branch:
        if details.get("size", 0) not in (0, None):
            return jsonify({"ok": False, "message": "The repository has no default branch yet."}), 400
        branch = "main"
        tree, initialization_error = initialize_empty_repository(
            session,
            normalized_repo,
            repo_path,
            branch,
        )
        if initialization_error:
            return jsonify({"ok": False, "message": initialization_error[0]}), initialization_error[1]
        return jsonify({
            "ok": True,
            "message": f"Initialized {normalized_repo} with the Files and Placeholder apps.",
            "repo": normalized_repo,
            "tree": tree,
            "initialized": True,
        })

    tree_path = f"{repo_path}/git/trees/{quote(branch, safe='')}?recursive=1"
    tree_status, tree_data = github_request(session["token"], tree_path)
    if tree_status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if tree_status == 404 and details.get("size", 0) == 0:
        tree, initialization_error = initialize_empty_repository(
            session,
            normalized_repo,
            repo_path,
            branch,
        )
        if initialization_error:
            return jsonify({"ok": False, "message": initialization_error[0]}), initialization_error[1]
        return jsonify({
            "ok": True,
            "message": f"Initialized {normalized_repo} with the Files and Placeholder apps.",
            "repo": normalized_repo,
            "tree": tree,
            "initialized": True,
        })
    if tree_status != 200:
        return jsonify({"ok": False, "message": "Could not read the repository file tree."}), 502
    if tree_data.get("truncated"):
        return jsonify({"ok": False, "message": "This repository is too large to load as one file tree."}), 413
    entries = [
        entry for entry in tree_data.get("tree", [])
        if not entry.get("path", "").startswith(".bettercs/")
        and entry.get("path") != ".bettercs"
    ]
    existing_app_names = {
        entry["path"].split("/", 1)[1]
        for entry in entries
        if entry.get("path", "").startswith("Apps/")
        and entry["path"].count("/") == 1
        and entry["path"].endswith(".js")
    }
    missing_default_apps = set(DEFAULT_APP_SOURCES) - existing_app_names
    if not entries or missing_default_apps:
        tree, initialization_error = initialize_empty_repository(
            session,
            normalized_repo,
            repo_path,
            branch,
            existing_entries=entries,
        )
        if initialization_error:
            return jsonify({"ok": False, "message": initialization_error[0]}), initialization_error[1]
        return jsonify({
            "ok": True,
            "message": f"Initialized {normalized_repo} with the Files and Placeholder apps.",
            "repo": normalized_repo,
            "tree": tree,
            "initialized": True,
        })

    file_tree = build_tree(entries, normalized_repo, branch)
    tree_json = json.dumps(serialized_tree_for_storage(file_tree), separators=(",", ":"), ensure_ascii=False)
    contents_path = f"{repo_path}/contents/{quote(TREE_FILE_PATH, safe='/')}"
    contents_status, contents = github_request(
        session["token"],
        f"{contents_path}?ref={quote(branch, safe='')}",
    )

    if contents_status not in (200, 404):
        return jsonify({"ok": False, "message": "Could not prepare the BetterCS tree file in this repository."}), 502

    file_payload = {
        "message": "Update BetterCS repository file tree",
        "content": base64.b64encode(tree_json.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if contents_status == 200 and contents.get("sha"):
        file_payload["sha"] = contents["sha"]

    write_status, _ = github_request(
        session["token"],
        contents_path,
        method="PUT",
        payload=file_payload,
    )
    if write_status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if write_status not in (200, 201):
        return jsonify({"ok": False, "message": "GitHub could not save the BetterCS file tree. Check token write access."}), 502

    session["repo"] = normalized_repo
    session["branch"] = branch
    session["tree"] = file_tree
    session["base_files"] = {
        path: {
            "sha": node.get("sha"),
            "mode": node.get("mode", "100644"),
            "type": node.get("type", "blob"),
        }
        for path, node in iter_tree_files(file_tree["root"])
        if node.get("sha")
    }
    session["pending"] = {}
    save_sessions(sessions)
    return jsonify({
        "ok": True,
        "message": f"Linked {normalized_repo} as your BetterCS cloud storage.",
        "repo": normalized_repo,
        "tree": file_tree,
    })


@cloud_api.get("/api/session")
def get_session():
    session, error = require_session()
    if error:
        return error
    return jsonify({
        "ok": True,
        "username": session["username"],
        "repo": session["repo"],
        "treeLoaded": session["tree"] is not None,
    })


@cloud_api.get("/api/browser/page")
def get_browser_page():
    session, error = require_session()
    if error:
        return error

    requested_url = request.args.get("url", "").strip()
    if not requested_url:
        return jsonify({"ok": False, "message": "Enter a website address."}), 400

    page_html, final_url, fetch_error = fetch_public_html(requested_url)
    if fetch_error:
        return jsonify({"ok": False, "message": fetch_error}), 422
    return jsonify({"ok": True, "url": final_url, "html": page_html})


@cloud_api.get("/api/tree")
def get_tree():
    session, error = require_session()
    if error:
        return error
    if session["repo"] is None:
        return jsonify({"ok": False, "message": "Link a GitHub repository first."}), 409
    if session["tree"] is None:
        tree, error = restore_repository_tree(session)
        if error:
            return jsonify({"ok": False, "message": error[0]}), error[1]
    return jsonify({
        "ok": True,
        "repo": session["repo"],
        "tree": session["tree"],
        "pendingChanges": count_pending_changes(session),
    })


def require_repository_tree(session):
    if session["repo"] is None:
        return None, ("Link a GitHub repository first.", 409)
    if session["tree"] is None:
        tree, error = restore_repository_tree(session)
        if error:
            return None, error
    tree, error = ensure_default_apps(session, session["tree"])
    if error:
        return None, error
    return tree, None


@cloud_api.get("/api/apps")
def list_apps():
    session, error = require_session()
    if error:
        return error
    tree, tree_error = require_repository_tree(session)
    if tree_error:
        return jsonify({"ok": False, "message": tree_error[0]}), tree_error[1]

    apps_directory = get_tree_node(tree, "Apps")
    apps = []
    if apps_directory and apps_directory.get("type") == "directory":
        for filename, node in apps_directory["children"].items():
            if node.get("type") == "directory" or not filename.endswith(".js"):
                continue
            apps.append({
                "name": filename[:-3],
                "filename": filename,
            })

    return jsonify({"ok": True, "repo": session["repo"], "apps": apps})


@cloud_api.get("/api/apps/<string:app_name>")
def get_app_source(app_name):
    session, error = require_session()
    if error:
        return error
    tree, tree_error = require_repository_tree(session)
    if tree_error:
        return jsonify({"ok": False, "message": tree_error[0]}), tree_error[1]

    name = app_name[:-3] if app_name.endswith(".js") else app_name
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", name):
        return jsonify({"ok": False, "message": "Invalid app name."}), 400

    source, source_error = read_app_source(session, tree, name)
    if source_error:
        return jsonify({"ok": False, "message": source_error[0]}), source_error[1]
    return jsonify({"ok": True, "name": name, "source": source})


def read_app_source(session, tree, name):
    relative_path = f"Apps/{name}.js"
    node = get_tree_node(tree, relative_path)
    if node is None or node.get("type") == "directory":
        return None, (f"App {name} was not found in the repository.", 404)

    pending = session["pending"].get(relative_path)
    if pending is None and relative_path in session["pending"]:
        return None, (f"App {name} has been removed.", 404)
    if pending and "content" in pending:
        source = pending["content"]
    else:
        if not node.get("sha"):
            return None, (f"App {name} has no committed source yet.", 404)
        owner, repo_name = session["repo"].split("/", 1)
        repo_path = f"/repos/{quote(owner, safe='')}/{quote(repo_name, safe='')}"
        contents_path = f"{repo_path}/contents/{quote(relative_path, safe='/')}"
        status, contents = github_request(
            session["token"],
            f"{contents_path}?ref={quote(tree['branch'], safe='')}",
        )
        if status is None:
            return None, ("Could not contact GitHub. Try again later.", 502)
        if status != 200:
            return None, (f"Could not load app {name} from GitHub.", 502)
        try:
            source = base64.b64decode(contents.get("content", "")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None, (f"App {name} is not valid UTF-8 JavaScript.", 422)

    return source, None


@cloud_api.get("/Apps/<string:app_name>")
def serve_app_module(app_name):
    session, error = require_session()
    if error:
        return error
    tree, tree_error = require_repository_tree(session)
    if tree_error:
        return jsonify({"ok": False, "message": tree_error[0]}), tree_error[1]

    name = app_name[:-3] if app_name.endswith(".js") else app_name
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", name):
        return jsonify({"ok": False, "message": "Invalid app name."}), 400
    source, source_error = read_app_source(session, tree, name)
    if source_error:
        return jsonify({"ok": False, "message": source_error[0]}), source_error[1]

    return Response(source, mimetype="text/javascript", headers={"Cache-Control": "no-store"})


@cloud_api.post("/api/tree/operations")
def mutate_tree():
    session, error = require_session()
    if error:
        return error
    if session["repo"] is None or session["tree"] is None:
        return jsonify({"ok": False, "message": "Link a GitHub repository first."}), 409

    payload = request.get_json(silent=True) or {}
    try:
        tree = apply_tree_operation(session, payload)
    except TreeOperationError as error:
        return jsonify({"ok": False, "message": str(error)}), error.status

    return jsonify({
        "ok": True,
        "tree": tree,
        "pendingChanges": count_pending_changes(session),
    })


@cloud_api.post("/api/tree/push")
def push_tree():
    session, error = require_session()
    if error:
        return error
    if session["repo"] is None or session["tree"] is None:
        return jsonify({"ok": False, "message": "Link a GitHub repository first."}), 409
    if not session["pending"]:
        return jsonify({"ok": False, "message": "There are no pending tree changes to push."}), 409

    owner, name = session["repo"].split("/", 1)
    repo_path = f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    branch = session["tree"]["branch"]
    ref_path = f"{repo_path}/git/ref/heads/{quote(branch, safe='')}"
    status, ref = github_request(session["token"], ref_path)
    if status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if status != 200:
        return jsonify({"ok": False, "message": "Could not read the repository branch before pushing."}), 502

    parent_sha = ref.get("object", {}).get("sha")
    commit_status, parent_commit = github_request(
        session["token"],
        f"{repo_path}/git/commits/{quote(parent_sha or '', safe='')}",
    )
    if commit_status != 200:
        return jsonify({"ok": False, "message": "Could not read the current repository commit."}), 502

    entries = []
    for path, change in sorted(session["pending"].items()):
        if change is None:
            original = session["base_files"].get(path, {})
            entries.append({
                "path": path,
                "mode": original.get("mode", "100644"),
                "type": original.get("type", "blob"),
                "sha": None,
            })
        elif "content" in change:
            entries.append({
                "path": path,
                "mode": change.get("mode", "100644"),
                "type": "blob",
                "content": change["content"],
            })
        else:
            entries.append({
                "path": path,
                "mode": change.get("mode", "100644"),
                "type": change.get("type", "blob"),
                "sha": change["sha"],
            })

    tree_updated_at = datetime.now(timezone.utc).isoformat()
    session["tree"]["updatedAt"] = tree_updated_at
    metadata = json.dumps(
        serialized_tree_for_storage(session["tree"]),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    entries.append({
        "path": TREE_FILE_PATH,
        "mode": "100644",
        "type": "blob",
        "content": metadata,
    })

    create_tree_status, created_tree = github_request(
        session["token"],
        f"{repo_path}/git/trees",
        method="POST",
        payload={
            "base_tree": parent_commit.get("tree", {}).get("sha"),
            "tree": entries,
        },
    )
    if create_tree_status != 201:
        return jsonify({"ok": False, "message": "GitHub could not build the updated repository tree."}), 502

    commit_status, commit = github_request(
        session["token"],
        f"{repo_path}/git/commits",
        method="POST",
        payload={
            "message": str((request.get_json(silent=True) or {}).get("message") or "Update BetterCS cloud tree")[:200],
            "tree": created_tree.get("sha"),
            "parents": [parent_sha],
        },
    )
    if commit_status != 201:
        return jsonify({"ok": False, "message": "GitHub could not create the repository commit."}), 502

    update_status, _ = github_request(
        session["token"],
        f"{repo_path}/git/refs/heads/{quote(branch, safe='')}",
        method="PATCH",
        payload={"sha": commit.get("sha"), "force": False},
    )
    if update_status != 200:
        return jsonify({"ok": False, "message": "The repository changed while pushing. Refresh its tree before trying again."}), 409

    pushed_entries = [
        entry for entry in created_tree.get("tree", [])
        if entry.get("path") != TREE_FILE_PATH
        and not entry.get("path", "").startswith(".bettercs/")
    ]
    session["tree"] = build_tree(pushed_entries, session["repo"], branch)
    session["tree"]["updatedAt"] = tree_updated_at
    session["base_files"] = {
        path: {
            "sha": node.get("sha"),
            "mode": node.get("mode", "100644"),
            "type": node.get("type", "blob"),
        }
        for path, node in iter_tree_files(session["tree"]["root"])
        if node.get("sha")
    }
    session["pending"] = {}
    return jsonify({
        "ok": True,
        "message": f"Pushed the updated tree to {session['repo']}. ",
        "repo": session["repo"],
        "tree": session["tree"],
        "pendingChanges": 0,
        "commit": commit.get("sha"),
    })