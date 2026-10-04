import van from "../lib/van.js"

const request = async (path, options = {}) => {
    const response = await fetch(path, {
        ...options,
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
    })
    const result = await response.json().catch(() => ({}))

    if (!response.ok) {
        throw new Error(result.message || `Backend request failed (${response.status}).`)
    }

    return result
}

let switchRequestId = 0

export const signIn = (username, token) => request("/api/login", {
    method: "POST",
    body: JSON.stringify({username, token}),
})

export const linkRepository = repository => request("/api/repo", {
    method: "POST",
    body: JSON.stringify(repository),
})

export const getSession = () => request("/api/session")

export const getTree = () => request("/api/tree")

export const listApps = () => request("/api/apps")

export const getRadioStations = country => request(`/api/radio/stations?country=${encodeURIComponent(country)}`)

export const fetchBrowserPage = url => request(`/api/browser/page?${new URLSearchParams({url})}`)

export const SwitchApp = async (appName, mount = document.getElementById("app-host")) => {
    if (typeof appName !== "string" || !appName.trim()) {
        throw new TypeError("SwitchApp requires an app name.")
    }

    const name = appName.trim().replace(/\.js$/i, "")
    if (!/^[A-Za-z0-9_-][A-Za-z0-9_.-]*$/.test(name)) {
        throw new TypeError("App names may contain letters, numbers, dots, underscores, and hyphens.")
    }

    const target = typeof mount === "string" ? document.querySelector(mount) : mount
    if (!(target instanceof Element)) {
        throw new TypeError("SwitchApp requires a mounted app container.")
    }

    const requestId = ++switchRequestId
    let appModule
    try {
        appModule = await import(`/Apps/${encodeURIComponent(name)}.js?switch=${requestId}`)
    } catch (error) {
        throw new Error(`Could not load app ${name}: ${error.message}`)
    }

    if (requestId !== switchRequestId) return {ok: false, stale: true}

    const render = appModule.default ?? appModule.App
    if (typeof render !== "function") {
        throw new TypeError(`App ${name} must default-export a VanJS component function.`)
    }

    const content = render(van)
    if (!(content instanceof Node)) {
        throw new TypeError(`App ${name} did not return a DOM node.`)
    }

    const appRoot = document.createElement("div")
    appRoot.className = "running-app"
    appRoot.dataset.appName = name
    while (target.firstChild) target.removeChild(target.firstChild)
    target.appendChild(appRoot)
    van.add(appRoot, content)
    return {ok: true, name}
}

export const logout = () => request("/api/logout", {
    method: "POST",
    body: JSON.stringify({}),
})

const mutateTree = (operation, values = {}) => request("/api/tree/operations", {
    method: "POST",
    body: JSON.stringify({operation, ...values}),
})

export const addFile = (path, content) => mutateTree("add-file", {path, content})

export const removeFile = path => mutateTree("remove-file", {path})

export const editFile = (path, content) => mutateTree("edit-file", {path, content})

export const removeFolder = path => mutateTree("remove-folder", {path})

export const makeFolder = path => mutateTree("make-folder", {path})

export const renameFile = (path, newPath) => mutateTree("rename-file", {path, newPath})

export const renameFolder = (path, newPath) => mutateTree("rename-folder", {path, newPath})

export const pushTree = (message) => request("/api/tree/push", {
    method: "POST",
    body: JSON.stringify({message}),
})