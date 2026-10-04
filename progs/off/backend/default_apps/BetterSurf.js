export default function BetterSurf(van) {
    const {button, div, form, h2, iframe, input, label, p} = van.tags
    const pageUrl = van.state("")
    const addressValue = van.state("")
    const status = van.state("")

    const openPage = event => {
        event.preventDefault()
        const entered = addressValue.val.trim()
        const candidate = /^[a-z][a-z\d+.-]*:\/\//i.test(entered)
            ? entered
            : `https://${entered}`

        try {
            const parsed = new URL(candidate)
            if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
                throw new Error("Only HTTP and HTTPS sites can be opened.")
            }
            pageUrl.val = parsed.href
            status.val = ""
        } catch {
            status.val = "Enter a valid website address."
        }
    }

    return div({class: "better-surf-app"},
        h2("BetterSurf"),
        form({class: "better-surf-address", onsubmit: openPage},
            label({for: "better-surf-url"}, "Website address"),
            input({
                id: "better-surf-url",
                type: "text",
                inputmode: "url",
                name: "url",
                autocomplete: "url",
                placeholder: "https://example.com",
                value: () => addressValue.val,
                oninput: event => addressValue.val = event.currentTarget.value,
                required: true,
            }),
            button({type: "submit"}, "Go"),
        ),
        p({class: "better-surf-status", role: "status", "aria-live": "polite"}, () => status.val),
        () => pageUrl.val
            ? iframe({
                class: "better-surf-page",
                title: "Website contents",
                src: pageUrl.val,
                sandbox: "allow-scripts allow-forms",
                referrerpolicy: "no-referrer",
                allowfullscreen: true,
            })
            : div({class: "better-surf-empty"}),
    )
}
