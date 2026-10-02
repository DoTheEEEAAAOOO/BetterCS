const GITHUB_USER_API = "https://api.github.com/user"

export async function LogIn(username, token) {
    const requestedUsername = username.trim()

    if (!requestedUsername || !token.trim()) {
        return {ok: false, message: "Enter your GitHub username and token."}
    }

    try {
        const response = await fetch(GITHUB_USER_API, {
            headers: {
                Accept: "application/vnd.github+json",
                Authorization: `Bearer ${token}`,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        })

        if (response.status === 401) {
            return {ok: false, message: "GitHub rejected that token."}
        }

        if (!response.ok) {
            return {ok: false, message: "GitHub could not verify this login right now."}
        }

        const user = await response.json()
        if (user.login?.toLowerCase() !== requestedUsername.toLowerCase()) {
            return {ok: false, message: "That token belongs to a different GitHub username."}
        }

        return {ok: true, message: `Signed in as ${user.login}.`}
    } catch {
        return {ok: false, message: "Could not contact GitHub. Try again later."}
    }
}