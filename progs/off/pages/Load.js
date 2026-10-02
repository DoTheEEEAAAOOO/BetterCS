import van from "https://cdn.jsdelivr.net/npm/vanjs-core@1.6.1/src/van.js"

const {div, h6} = van.tags
const loading = van.state(true)
const message = van.state("Loading BetterCS...")

const Main = () => div({id: "loading-screen", class: "loading-screen"},
    div({
        "aria-busy": () => String(loading.val),
        "aria-hidden": "true",
        hidden: () => !loading.val,
    }),
    h6({role: "status", "aria-live": "polite"},
        () => message.val,
    ),
)

van.add(document.body, Main())

const loadWelcome = async () => {
    try {
        await document.fonts.ready
        message.val = "Opening BetterCS..."
        await import("./Welcome.js")
        document.getElementById("loading-screen")?.remove()
    } catch (error) {
        console.error("Unable to load the Welcome page:", error)
        loading.val = false
        message.val = "Unable to load BetterCS. Check your connection and reload."
    }
}

if (document.readyState === "complete") {
    loadWelcome()
} else {
    window.addEventListener("load", loadWelcome, {once: true})
}