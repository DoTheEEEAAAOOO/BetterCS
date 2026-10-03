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