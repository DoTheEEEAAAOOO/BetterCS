import van from "../lib/van.js"
import {BottomBar} from "../components/BottomBar.js"
import {listApps, logout, SwitchApp} from "../frontend/api.js"
import {toggleMusic} from "./Welcome.js"

const {div, main, p} = van.tags
const logoutStatus = van.state("")

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

    const appHost = div({id: "app-host", "aria-live": "polite"})
    const openApp = async name => {
        try {
            await SwitchApp(name, appHost)
        } catch (error) {
            logoutStatus.val = error.message
        }
    }
    const firstApp = apps[0]

    const page = div(
        main({id: "main-content"},
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
                    items: [{label: "Reload BetterCS", onSelect: reloadApp}, {label: "Mute/unmute audio", onSelect: toggleMusic}],
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