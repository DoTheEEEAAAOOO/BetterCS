import van from "../lib/van.js"
import {BottomBar} from "../components/BottomBar.js"
import {logout} from "../frontend/api.js"

const {div, h1, main, p} = van.tags
const logoutStatus = van.state("")

const focusHome = () => document.getElementById("main-title")?.focus()
const reloadApp = () => window.location.reload()
const logOut = async () => {
    try {
        await logout()
        window.location.assign("/")
    } catch (error) {
        logoutStatus.val = error.message
    }
}

export const Main = () => div(
    main({id: "main-content"},
        h1({id: "main-title", tabindex: -1}, "BetterCS"),
        p("Your BetterCS session is active."),
        p({role: "status", "aria-live": "polite"}, () => logoutStatus.val),
    ),
    BottomBar({
        id: "main-bottom-bar",
        label: "Main quick menu",
        Menu: [
            {
                id: "page",
                label: "Page",
                items: [{label: "Focus home", onSelect: focusHome}],
            },
            {
                id: "system",
                label: "System",
                items: [{label: "Reload BetterCS", onSelect: reloadApp}],
            },
            {
                id: "account",
                label: "Account",
                items: [{label: "Log out", onSelect: logOut}],
            },
        ],
        ListBar: [
            {id: "page-home", label: "Home", onClick: focusHome},
            {id: "page-reload", label: "Reload", onClick: reloadApp},
        ],
    })
)