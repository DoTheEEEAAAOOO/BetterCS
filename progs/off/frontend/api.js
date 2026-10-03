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