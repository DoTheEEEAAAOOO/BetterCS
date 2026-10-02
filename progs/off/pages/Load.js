import van from "https://cdn.jsdelivr.net/npm/vanjs-core@1.6.1/src/van.js"

const {div, h6} = van.tags
const resourcesReady = van.state(false)

const Main = () => div({class: "loading-screen"},
    div({
        "aria-busy": () => String(!resourcesReady.val),
        "aria-hidden": "true",
        hidden: () => resourcesReady.val,
    }),
    h6({role: "status", "aria-live": "polite"},
        () => resourcesReady.val ? "Resources ready." : "Loading BetterCS...",
    ),
)

van.add(document.body, Main())

const markResourcesReady = () => {
    document.fonts.ready.then(() => {
        resourcesReady.val = true
    })
}

if (document.readyState === "complete") {
    markResourcesReady()
} else {
    window.addEventListener("load", markResourcesReady, {once: true})
}