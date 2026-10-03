import base64
import json
import re
import secrets
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, request


cloud_api = Blueprint("cloud_api", __name__)
sessions = {}
GITHUB_API = "https://api.github.com"
TREE_FILE_PATH = ".bettercs/tree.json"
SESSION_COOKIE = "bettercs_session"


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


def current_session():
    session_id = request.cookies.get(SESSION_COOKIE)
    return sessions.get(session_id) if session_id else None


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
    sessions[session_id] = {
        "token": token,
        "username": user["login"],
        "repo": None,
        "tree": None,
        "base_files": {},
        "pending": {},
    }
    response = jsonify({"ok": True, "message": f"Signed in as {user['login']}.", "username": user["login"]})
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        secure=request.is_secure,
        samesite="Lax",
        max_age=86400,
        path="/api",
    )
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
                "auto_init": True,
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
    if details.get("permissions", {}).get("push") is False:
        return jsonify({"ok": False, "message": "This GitHub token cannot write to that repository."}), 403

    branch = details.get("default_branch")
    if not branch:
        return jsonify({"ok": False, "message": "The repository has no default branch yet."}), 400

    tree_path = f"{repo_path}/git/trees/{quote(branch, safe='')}?recursive=1"
    tree_status, tree_data = github_request(session["token"], tree_path)
    if tree_status is None:
        return jsonify({"ok": False, "message": "Could not contact GitHub. Try again later."}), 502
    if tree_status != 200:
        return jsonify({"ok": False, "message": "Could not read the repository file tree."}), 502
    if tree_data.get("truncated"):
        return jsonify({"ok": False, "message": "This repository is too large to load as one file tree."}), 413

    normalized_repo = f"{owner}/{name}"
    entries = [
        entry for entry in tree_data.get("tree", [])
        if not entry.get("path", "").startswith(".bettercs/")
        and entry.get("path") != ".bettercs"
    ]
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


@cloud_api.get("/api/tree")
def get_tree():
    session, error = require_session()
    if error:
        return error
    if session["repo"] is None or session["tree"] is None:
        return jsonify({"ok": False, "message": "Link a GitHub repository first."}), 409
    return jsonify({
        "ok": True,
        "repo": session["repo"],
        "tree": session["tree"],
        "pendingChanges": count_pending_changes(session),
    })


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