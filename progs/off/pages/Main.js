import van from "../lib/van.js"
import {BottomBar} from "../components/BottomBar.js"
import {listApps, logout, SwitchApp} from "../frontend/api.js"

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

export const Main = async () => {
    let apps = []
    try {
        apps = (await listApps()).apps
    } catch (error) {
        logoutStatus.val = error.message
    }

    const activeApp = van.state("")
    const appHost = div({id: "app-host", "aria-live": "polite"},
        h1("BetterCS"),
        p("Choose an app from the bottom bar."),
    )
    const openApp = async name => {
        try {
            const result = await SwitchApp(name, appHost)
            if (result.ok) activeApp.val = result.name
        } catch (error) {
            logoutStatus.val = error.message
        }
    }
    const firstApp = apps[0]

    const page = div(
        main({id: "main-content"},
            h1({id: "main-title", tabindex: -1}, "BetterCS"),
            p(() => activeApp.val ? `Running ${activeApp.val}` : "Your BetterCS session is active."),
            p({role: "status", "aria-live": "polite"}, () => logoutStatus.val),
            appHost,
        ),
        BottomBar({
            id: "main-bottom-bar",
            label: "Main quick menu",
            Menu: [
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
            ListBar: apps.map(app => ({
                id: `app-${app.name}`,
                label: app.name,
                onClick: () => openApp(app.name),
            })),
        })
    )

    if (firstApp) {
        requestAnimationFrame(() => openApp(firstApp.name))
    }
    return page
}