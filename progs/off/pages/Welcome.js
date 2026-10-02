import van from "../lib/van.js"
import {Notif} from "../components/Notif.js"
import {Tabs} from "../components/Tabs.js"
import {LogIn} from "../backend/LogIn.js"

const audio = new Audio("./../audio/chillax.mp3");
audio.loop = true;
audio.play().catch(() => {});

const {a, button, div, form, h1, header, input, label, main, p} = van.tags
const loginStatus = van.state("")
const loginBusy = van.state(false)

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
        const result = await LogIn(username, token)
        loginStatus.val = result.message
        if (result.ok) loginForm.elements.namedItem("token").value = ""
    } finally {
        loginBusy.val = false
    }
}

const Main = () => div(
    header(h1("Welcome to BetterCS")),
    main(
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
                        p("Sign in with your GitHub username and personal access token. The token is only sent to GitHub to verify your account; this app does not save it."),
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
                }
            ]
        })
    ),
)

van.add(document.body, Main())