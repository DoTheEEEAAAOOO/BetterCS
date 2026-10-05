import van from "../../node_modules/vanjs-core/src/van.js"

const {a, button, dd, div, dl, dt, h1, h2, header, input, label, main, nav, p, section, span} = van.tags

const apps = van.state([])
const loading = van.state(true)
const loadError = van.state("")
const selected = van.state(null)
const installing = van.state(false)
const installStatus = van.state("")
const installForm = van.state(false)
const installUsername = van.state("")
const installRepo = van.state("")
const installToken = van.state("")

const loadApps = async () => {
    loading.val = true
    loadError.val = ""
    try {
        const response = await fetch("/api/apps")
        const data = await response.json()
        if (!response.ok || !data.ok) {
            loadError.val = data.message || "Could not load the app catalog."
            return
        }
        apps.val = Array.isArray(data.apps) ? data.apps : []
    } catch {
        loadError.val = "Could not contact the BetterStore server."
    } finally {
        loading.val = false
    }
}

const installApp = async (app) => {
    if (installing.val) return
    installing.val = true
    installStatus.val = ""
    try {
        const response = await fetch("/api/install", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                file: app.file,
                username: installUsername.val,
                repo: installRepo.val,
                token: installToken.val,
            }),
        })
        let data = {}
        try {
            data = await response.json()
        } catch {
            data = {}
        }
        if (!response.ok || !data.ok) {
            installStatus.val = data.message || `Could not install ${app.name}.`
            return
        }
        installStatus.val = data.message || `${app.name} was installed.`
        installForm.val = false
        installToken.val = ""
    } catch {
        installStatus.val = "Could not contact the BetterStore server."
    } finally {
        installing.val = false
    }
}

const AppTile = (app) => button({
    class: "store-app-tile",
    type: "button",
    onclick: () => {
        selected.val = app
        installForm.val = false
        installStatus.val = ""
    },
},
    span({class: "store-app-tile-icon", "aria-hidden": "true"}, String(app.name || "?").trim().charAt(0).toUpperCase()),
    span({class: "store-app-tile-name"}, app.name),
)

const AppGrid = () => div({class: "store-app-grid"},
    apps.val.map(app => AppTile(app)),
)

const InstallForm = (app) => div({class: "store-install-form"},
    p("Enter your GitHub details to install this app directly into your repository."),
    label({class: "store-field"},
        span("GitHub username"),
        input({
            type: "text",
            placeholder: "e.g. atoz",
            value: installUsername,
            oninput: event => installUsername.val = event.target.value,
            autocomplete: "off",
        }),
    ),
    label({class: "store-field"},
        span("Repository"),
        input({
            type: "text",
            placeholder: "owner/repository or a GitHub repo URL",
            value: installRepo,
            oninput: event => installRepo.val = event.target.value,
            autocomplete: "off",
        }),
    ),
    label({class: "store-field"},
        span("GitHub token"),
        input({
            type: "password",
            placeholder: "Token with repo access",
            value: installToken,
            oninput: event => installToken.val = event.target.value,
            autocomplete: "off",
        }),
    ),
    div({class: "store-install-actions"},
        button({
            class: "store-install",
            type: "button",
            disabled: installing,
            onclick: () => installApp(app),
        }, () => installing.val ? "Installing..." : "Install"),
        button({
            class: "store-cancel",
            type: "button",
            onclick: () => {
                installForm.val = false
                installStatus.val = ""
            },
        }, "Cancel"),
    ),
    p({class: "store-status"}, installStatus),
)

const AppDetail = (app) => section({class: "store-app-detail"},
    button({
        class: "store-back",
        type: "button",
        onclick: () => {
            selected.val = null
            installForm.val = false
            installStatus.val = ""
        },
    }, "Back to all apps"),
    h2(app.name),
    dl({class: "store-app-meta"},
        div({class: "store-app-meta-row"},
            dt("Description"),
            dd(app.description || "—"),
        ),
        div({class: "store-app-meta-row"},
            dt("Version"),
            dd(app.version || "—"),
        ),
        div({class: "store-app-meta-row"},
            dt("Author"),
            dd(app.author || "—"),
        ),
    ),
    () => installForm.val ? InstallForm(app) : button({
        class: "store-install",
        type: "button",
        onclick: () => {
            installForm.val = true
            installStatus.val = ""
        },
    }, "Install"),
    () => installForm.val ? null : p({class: "store-status"}, installStatus),
)

const Catalog = () => section({class: "store-catalog"},
    h2("Apps"),
    () => loading.val
        ? p({class: "store-loading"}, "Loading the app catalog...")
        : loadError.val
            ? p({class: "store-error"}, loadError.val)
            : apps.val.length === 0
                ? p({class: "store-empty"}, "No apps are available in the store right now.")
                : AppGrid(),
)

export const Main = () => div(
    header(
        h1("BetterStore"),
        p("A application store for BetterCS, where you can find and download applications for your BetterCS device."),
        nav(
            a({href: "Sdk.html"}, "SDK"),
            a({href: "index.html"}, "Home"),
        ),
    ),
    main(
        () => selected.val ? AppDetail(selected.val) : Catalog(),
    ),
)

van.add(document.body, Main())
loadApps()
