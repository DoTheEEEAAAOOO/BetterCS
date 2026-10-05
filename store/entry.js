const http = require("http");
const fs = require("fs");
const path = require("path");

const contentTypes = {
    ".css": "text/css",
    ".html": "text/html",
    ".js": "text/javascript",
    ".ttf": "font/ttf",
    ".xml": "application/xml",
    ".json": "application/json",
};

const githubApiUrl = process.env.GITHUB_API_URL || "https://api.github.com";
const appsDir = path.join(__dirname, "apps");

const parseAppXml = (text) => {
    const metadata = text.match(/<Metadata>([\s\S]*?)<\/Metadata>/);
    const code = text.match(/<Code>([\s\S]*?)<\/Code>/);
    if (!metadata) return null;
    const field = (tag) => {
        const match = metadata[1].match(new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`));
        return match ? match[1].trim() : "";
    };
    return {
        name: field("Name"),
        description: field("Description"),
        version: field("Version"),
        author: field("Author"),
        code: code ? code[1].trim() : "",
    };
};

const sendJson = (res, status, value) => {
    res.writeHead(status, {"Content-Type": "application/json"});
    res.end(JSON.stringify(value));
};

class InstallError extends Error {
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}

const githubRequest = async (token, requestPath, method = "GET", payload = null) => {
    const options = {
        method,
        headers: {
            "Accept": "application/vnd.github+json",
            "Authorization": `Bearer ${token}`,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "BetterStore",
        },
    };
    if (payload) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(payload);
    }

    let response;
    try {
        response = await fetch(`${githubApiUrl}${requestPath}`, options);
    } catch {
        throw new InstallError(502, "Could not contact GitHub. Try again later.");
    }

    let data = {};
    try {
        data = await response.json();
    } catch {
        data = {};
    }
    return {status: response.status, data};
};

const normalizeRepository = (value) => String(value || "")
    .trim()
    .replace(/^https?:\/\/github\.com\//i, "")
    .replace(/\.git$/, "")
    .replace(/^\/+|\/+$/g, "");

const resolveInstallTarget = async (app, credentials) => {
    const username = String(credentials.username || "").trim();
    const repository = normalizeRepository(credentials.repo);
    const token = String(credentials.token || "").trim();

    if (!/^[A-Za-z0-9][A-Za-z0-9-]*$/.test(username)) {
        throw new InstallError(400, "Enter your GitHub username.");
    }
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
        throw new InstallError(400, "Use the format owner/repository for the repository.");
    }
    if (!token) {
        throw new InstallError(400, "Enter a GitHub token.");
    }

    const userResult = await githubRequest(token, "/user");
    if (userResult.status === 401) {
        throw new InstallError(401, "GitHub rejected that token.");
    }
    if (userResult.status !== 200) {
        throw new InstallError(502, "Could not contact GitHub. Try again later.");
    }
    if (String(userResult.data.login || "").toLowerCase() !== username.toLowerCase()) {
        throw new InstallError(403, "That token belongs to a different GitHub username.");
    }

    const [owner, name] = repository.split("/");
    const repoPath = `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`;
    const repoResult = await githubRequest(token, repoPath);
    if (repoResult.status !== 200) {
        throw new InstallError(403, "Repository not found or not accessible with this token.");
    }
    if (repoResult.data.permissions?.push === false) {
        throw new InstallError(403, "This GitHub token cannot write to that repository.");
    }
    const branch = repoResult.data.default_branch;
    if (!branch) {
        throw new InstallError(400, "The repository has no default branch yet.");
    }

    return {repository, branch, repoPath, token, targetPath: `Apps/${app.name}.js`};
};

const installAppOnGitHub = async (app, credentials) => {
    const {repository, branch, repoPath, token, targetPath} = await resolveInstallTarget(app, credentials);

    const refPath = `${repoPath}/git/ref/heads/${encodeURIComponent(branch)}`;
    const refsPath = `${repoPath}/git/refs/heads/${encodeURIComponent(branch)}`;
    const contentsResult = await githubRequest(
        token,
        `${repoPath}/contents/${encodeURIComponent(targetPath)}?ref=${encodeURIComponent(branch)}`,
    );
    if (contentsResult.status === 200) {
        throw new InstallError(409, `${app.name} is already installed in that repository.`);
    }

    let parentSha = null;
    let parentTreeSha = null;
    const refResult = await githubRequest(token, refPath);
    if (refResult.status === 200) {
        parentSha = refResult.data.object?.sha;
        const commitResult = await githubRequest(
            token,
            `${repoPath}/git/commits/${encodeURIComponent(parentSha || "")}`,
        );
        if (commitResult.status !== 200) {
            throw new InstallError(502, "Could not read the repository's current commit.");
        }
        parentTreeSha = commitResult.data.tree?.sha;
    } else if (refResult.status !== 404) {
        throw new InstallError(502, "Could not inspect the repository branch before installing.");
    }

    const treePayload = {
        tree: [{path: targetPath, mode: "100644", type: "blob", content: app.code}],
    };
    if (parentTreeSha) {
        treePayload.base_tree = parentTreeSha;
    }

    const treeResult = await githubRequest(token, `${repoPath}/git/trees`, "POST", treePayload);
    if (treeResult.status !== 201) {
        throw new InstallError(502, "GitHub could not create the updated repository tree.");
    }

    const newCommit = await githubRequest(token, `${repoPath}/git/commits`, "POST", {
        message: `Add ${app.name} from BetterStore`,
        tree: treeResult.data.sha,
        parents: parentSha ? [parentSha] : [],
    });
    if (newCommit.status !== 201) {
        throw new InstallError(502, "GitHub could not create the repository commit.");
    }

    const writeResult = parentSha
        ? await githubRequest(token, refsPath, "PATCH", {sha: newCommit.data.sha, force: false})
        : await githubRequest(token, `${repoPath}/git/refs`, "POST", {ref: `refs/heads/${branch}`, sha: newCommit.data.sha});
    if (writeResult.status !== 200 && writeResult.status !== 201) {
        throw new InstallError(409, "The repository changed while installing. Try again.");
    }

    return {repository, branch, commit: newCommit.data.sha};
};

const uninstallAppOnGitHub = async (app, credentials) => {
    const {repository, branch, repoPath, token, targetPath} = await resolveInstallTarget(app, credentials);

    const contentsResult = await githubRequest(
        token,
        `${repoPath}/contents/${encodeURIComponent(targetPath)}?ref=${encodeURIComponent(branch)}`,
    );
    if (contentsResult.status === 404) {
        throw new InstallError(404, `${app.name} is not installed in that repository.`);
    }
    if (contentsResult.status !== 200) {
        throw new InstallError(502, "Could not read the app file from the repository.");
    }
    const fileSha = contentsResult.data.sha;
    if (!fileSha) {
        throw new InstallError(502, "The app file in the repository has no commit hash.");
    }

    const deleteResult = await githubRequest(
        token,
        `${repoPath}/contents/${encodeURIComponent(targetPath)}`,
        "DELETE",
        {message: `Remove ${app.name} via BetterStore`, sha: fileSha, branch},
    );
    if (deleteResult.status !== 200) {
        throw new InstallError(502, "GitHub could not remove the app file.");
    }

    return {repository, branch, commit: deleteResult.data?.commit?.sha};
};

const listApps = (res) => {
    fs.readdir(appsDir, (err, files) => {
        if (err) {
            sendJson(res, 500, {ok: false, message: "Could not read the app catalog."});
            return;
        }

        const apps = files
            .filter(file => file.endsWith(".xml"))
            .map(file => {
                const app = parseAppXml(fs.readFileSync(path.join(appsDir, file), "utf8"));
                return app && app.name ? {file, ...app} : null;
            })
            .filter(Boolean);
        sendJson(res, 200, {ok: true, apps});
    });
};

const handleAppRequest = (req, res, action) => {
    let body = "";
    req.on("data", chunk => {
        body += chunk;
        if (body.length > 1e6) req.destroy();
    });
    req.on("end", async () => {
        let payload;
        try {
            payload = JSON.parse(body || "{}");
        } catch {
            sendJson(res, 400, {ok: false, message: "Invalid request."});
            return;
        }

        const file = String(payload.file || "");
        if (!/^[A-Za-z0-9_.-]+\.xml$/.test(file)) {
            sendJson(res, 400, {ok: false, message: "Invalid app file."});
            return;
        }

        try {
            const text = await fs.promises.readFile(path.join(appsDir, file), "utf8");
            const app = parseAppXml(text);
            if (!app || !app.name || !app.code) {
                sendJson(res, 422, {ok: false, message: "That app's metadata is incomplete."});
                return;
            }

            const result = await action(app, payload);
            sendJson(res, 200, result);
        } catch (error) {
            if (error && error.code === "ENOENT") {
                sendJson(res, 404, {ok: false, message: "That app does not exist."});
                return;
            }
            if (error instanceof InstallError) {
                sendJson(res, error.status, {ok: false, message: error.message});
                return;
            }
            sendJson(res, 500, {ok: false, message: "The request failed unexpectedly."});
        }
    });
};

const installApp = (req, res) => handleAppRequest(req, res, async (app, payload) => {
    const result = await installAppOnGitHub(app, payload);
    return {
        ok: true,
        message: `Installed ${app.name} into ${result.repository}. Sign out and back in on BetterCS to see it in your app list.`,
        repo: result.repository,
        branch: result.branch,
        commit: result.commit,
    };
});

const uninstallApp = (req, res) => handleAppRequest(req, res, async (app, payload) => {
    const result = await uninstallAppOnGitHub(app, payload);
    return {
        ok: true,
        message: `Removed ${app.name} from ${result.repository}. Sign out and back in on BetterCS to see it disappear from your app list.`,
        repo: result.repository,
        branch: result.branch,
        commit: result.commit,
    };
});

const safePath = (base, requestPath) => {
    const file = path.join(base, requestPath);
    return file === base || file.startsWith(`${base}${path.sep}`) ? file : null;
};

const server = http.createServer((req, res) => {
    const requestPath = new URL(req.url, "http://localhost").pathname;

    if (req.method === "GET" && requestPath === "/api/apps") {
        listApps(res);
        return;
    }

    if (req.method === "POST" && requestPath === "/api/install") {
        installApp(req, res);
        return;
    }

    if (req.method === "POST" && requestPath === "/api/uninstall") {
        uninstallApp(req, res);
        return;
    }

    const file = requestPath.startsWith("/assets/") || requestPath.startsWith("/node_modules/") || requestPath.startsWith("/apps/")
        ? safePath(__dirname, requestPath)
        : safePath(path.join(__dirname, "ui"), requestPath === "/" ? "index.html" : requestPath);
    if (!file) {
        res.writeHead(400);
        res.end("400");
        return;
    }

    fs.readFile(file, (err, data) => {
        if (err) {
            res.writeHead(404);
            res.end("404");
            return;
        }

        res.writeHead(200, {
            "Content-Type": contentTypes[path.extname(file)] || "application/octet-stream"
        });
        res.end(data);
    });
});

server.listen(3000, "127.0.0.1", () => {
    console.log("running at http://localhost:3000");
});
