import van from "../lib/van.js"
import {Notif} from "../components/Notif.js"
import {Tabs} from "../components/Tabs.js"
import {getSession, getTree, linkRepository, signIn} from "../frontend/api.js"

const {a, button, div, form, h1, header, input, label, main, p, pre} = van.tags
const loginStatus = van.state("")
const loginBusy = van.state(false)
const repoStatus = van.state("")
const repoBusy = van.state(false)
const linkedRepo = van.state("")
const repoMode = van.state("existing")
const sessionStatus = van.state("")
const sessionBusy = van.state(false)
const sessionUsername = van.state("")
const treeJson = van.state("")
const musicEnabled = van.state(false)
const musicStatus = van.state("")

const audio = new Audio("/audio/chillax.mp3")
audio.loop = true
audio.preload = "auto"
audio.play().then(() => {
    musicEnabled.val = !audio.muted
}).catch(() => {})

const toggleMusic = async () => {
    musicStatus.val = ""

    if (audio.paused) {
        audio.muted = false
        try {
            await audio.play()
            musicEnabled.val = true
        } catch {
            musicStatus.val = "Music could not start. Check that the audio file is available."
        }
        return
    }

    audio.muted = !audio.muted
    musicEnabled.val = !audio.muted
}

const openStepTwo = () => {
    requestAnimationFrame(() => {
        document.getElementById("welcome-tabs-tab-2")?.click()
    })
}

const openStepThree = () => {
    requestAnimationFrame(() => {
        document.getElementById("welcome-tabs-tab-3")?.click()
    })
}

const submitLogin = async event => {
    event.preventDefault()
    if (loginBusy.val) return

    const loginForm = event.currentTarget
    const formData = new FormData(loginForm)
    const username = formData.get("username")?.toString() ?? ""
    const token = formData.get("token")?.toString() ?? ""

    loginBusy.val = true
    loginStatus.val = ""

    try {
        const result = await signIn(username, token)
        loginStatus.val = result.message

        if (result.ok) {
            linkedRepo.val = ""
            repoStatus.val = ""
            repoMode.val = "existing"
            sessionStatus.val = ""
            treeJson.val = ""
            loginForm.elements.namedItem("token").value = ""
            openStepTwo()
        }
    } catch (error) {
        loginStatus.val = error.message
    } finally {
        loginBusy.val = false
    }
}

const submitRepoLink = async event => {
    event.preventDefault()
    if (repoBusy.val) return

    const repoForm = event.currentTarget
    const formData = new FormData(repoForm)
    const mode = formData.get("mode")?.toString() ?? "existing"
    const repoValue = formData.get("repo")?.toString().trim() ?? ""

    repoBusy.val = true
    repoStatus.val = ""

    try {
        const result = await linkRepository({mode, repo: repoValue})
        linkedRepo.val = result.repo
        repoStatus.val = result.message
        repoForm.elements.namedItem("repo").value = result.repo.split("/").at(-1)
        openStepThree()
    } catch (error) {
        repoStatus.val = error.message
    } finally {
        repoBusy.val = false
    }
}

const submitStepThree = async () => {
    if (sessionBusy.val) return

    sessionBusy.val = true
    sessionStatus.val = ""
    treeJson.val = ""

    try {
        const session = await getSession()
        if (!session.repo) {
            throw new Error("Link a GitHub repository in Step 2 first.")
        }

        const result = await getTree()
        sessionUsername.val = session.username
        linkedRepo.val = result.repo
        treeJson.val = JSON.stringify(result.tree, null, 2)
        sessionStatus.val = `Signed in as ${session.username}. Repository tree loaded from ${result.repo}.`
    } catch (error) {
        sessionStatus.val = error.message
    } finally {
        sessionBusy.val = false
    }
}

const Main = () => div(
    header(
        h1("Welcome to BetterCS"),
        button({class: "music-toggle", type: "button", onclick: toggleMusic},
            () => musicEnabled.val ? "Mute music" : "Play music",
        ),
    ),
    main(
        p({role: "status", "aria-live": "polite"}, () => musicStatus.val),
        Notif(
            "Thank you for installing BetterCS!",
            "It is really nice for me (the owner) to see that you are using BetterCS. I hope you enjoy it! It makes me really happy to see someone use my project.",
        ),
        Tabs({
            id: "welcome-tabs",
            label: "Welcome Tabs",
            tabs: [
                {
                    label: "The Experience",
                    content: div(
                        h1("The Experience"),
                        p("BetterCS is a better experience for you using your computer, if you want control and power while keeping everything stable, secure, on cloud, and familiar for you if you are a SmartTV user. Looks pretty nostalgic too in my opinion!"),
                        p("It might look pretty tough if you never used a SmartTV, Tablet, Phone, or Computer before, but it is actually pretty simple to use. It is organized like Tizen, ensuring you have the app content, a pop-out menu bar, and a home screen that is not shoved into your face at first."),
                        p("Regarding so, welcome! The community will welcome you with open arms, and I hope you enjoy your time here. If you have any questions or feedback, please contact me on GitHub as a GitHub issue, repo is on this link:"),
                        p({style: "text-align: center;"},
                            a({href: "https://github.com/BetterCS/BetterCS"}, "BetterCS on GitHub"),
                        ),
                    ),
                },
                {
                    label: "OOBE: Step 1",
                    content: div(
                        h1("OOBE: Step 1"),
                        p("Welcome to the Out-of-the-Box Experience! This is the first step in setting up your new BetterCS installation."),
                        p("In this step, you will be asked to link your BetterCS installation to your BetterCS account. This is required to use BetterCS, as it allows you to access cloud features, such as syncing your settings and data across devices, using the free & unlimited cloud storage, and accessing the BetterCS Store."),
                        p("Sign in with your GitHub username and personal access token. The frontend sends it to the BetterCS backend, which verifies it with GitHub and keeps it in server memory for this session. It is not written to disk."),
                        form({class: "github-login", onsubmit: submitLogin},
                            label({for: "github-username"}, "GitHub username"),
                            input({
                                type: "text",
                                id: "github-username",
                                name: "username",
                                autocomplete: "username",
                                required: true,
                            }),
                            label({for: "github-token"}, "GitHub token"),
                            input({
                                type: "password",
                                id: "github-token",
                                name: "token",
                                autocomplete: "off",
                                required: true,
                            }),
                            button({type: "submit", disabled: () => loginBusy.val},
                                () => loginBusy.val ? "Checking..." : "Sign in",
                            ),
                            p({role: "status", "aria-live": "polite"}, () => loginStatus.val),
                        ),
                    ),
                },
                {
                    label: "OOBE: Step 2",
                    content: div(
                        h1("OOBE: Step 2"),
                        p("This is the second step in setting up BetterCS. Link a GitHub repository to use as the cloud storage for BetterCS."),
                        p("Your GitHub repository will be used as the cloud storage for BetterCS. The backend reads the repository tree, keeps it in RAM for this session, and stores its JSON representation in the repository. You can use an existing repository or have BetterCS create a private one."),
                        form({class: "github-repo-link", onsubmit: submitRepoLink},
                            div({class: "repo-modes"},
                                label({class: "repo-mode-choice"},
                                    input({
                                        type: "radio",
                                        name: "mode",
                                        value: "existing",
                                        checked: () => repoMode.val === "existing",
                                        onchange: () => repoMode.val = "existing",
                                    }),
                                    "Use an existing repository",
                                ),
                                label({class: "repo-mode-choice"},
                                    input({
                                        type: "radio",
                                        name: "mode",
                                        value: "create",
                                        checked: () => repoMode.val === "create",
                                        onchange: () => repoMode.val = "create",
                                    }),
                                    "Create a private repository automatically",
                                ),
                            ),
                            () => repoMode.val === "existing"
                                ? div(
                                    label({for: "github-repo"}, "GitHub repository"),
                                    input({
                                        type: "text",
                                        id: "github-repo",
                                        name: "repo",
                                        placeholder: "owner/repository",
                                        autocomplete: "off",
                                        required: true,
                                    }),
                                )
                                : div(
                                    label({for: "github-repo-name"}, "New repository name"),
                                    input({
                                        type: "text",
                                        id: "github-repo-name",
                                        name: "repo",
                                        value: "bettercs-cloud",
                                        autocomplete: "off",
                                        required: true,
                                    }),
                                ),
                            button({type: "submit", disabled: () => repoBusy.val},
                                () => repoBusy.val
                                    ? "Linking..."
                                    : repoMode.val === "create" ? "Create private repo & link" : "Link repository",
                            ),
                            p({role: "status", "aria-live": "polite"}, () => repoStatus.val || (linkedRepo.val ? `Currently linked: ${linkedRepo.val}` : "")),
                        ),
                    ),
                },
                {
                    label: "OOBE: Step 3",
                    content: div(
                        h1("OOBE: Step 3"),
                        p("Sign in to BetterCS with the GitHub account and repository you linked in the previous steps."),
                        button({type: "button", onclick: submitStepThree, disabled: () => sessionBusy.val},
                            () => sessionBusy.val ? "Loading..." : "Log in to BetterCS",
                        ),
                        p({role: "status", "aria-live": "polite"}, () => sessionStatus.val),
                        () => treeJson.val ? pre({class: "repo-tree"}, treeJson.val) : null,
                    ),
                },
            ],
            initialTab: 0,
        })
    ),
)

van.add(document.body, Main())