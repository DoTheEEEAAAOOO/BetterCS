import van from "https://cdn.jsdelivr.net/npm/vanjs-core@1.6.1/src/van.js"

const {button, div, p, strong} = van.tags

export const Notif = (title, message, duration = 9000) => {
    const visible = van.state(true)
    let timeoutId
    const dismiss = event => {
        if (timeoutId) window.clearTimeout(timeoutId)
        visible.val = false
        event?.currentTarget?.closest(".notif")?.remove()
    }

    if (duration > 0) timeoutId = window.setTimeout(() => dismiss(), duration)

    return div({class: "notif", hidden: () => !visible.val},
        div({class: "notif-copy", role: "status", "aria-live": "polite"},
            strong(title),
            p(message),
        ),
        button({
            class: "notif-dismiss",
            type: "button",
            "aria-label": "Dismiss notification",
            onclick: dismiss,
        }, "×"),
    )
}