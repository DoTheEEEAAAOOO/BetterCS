import {fetchBrowserPage} from "../frontend/api.js"

export default function BetterSurf(van) {
    const {button, div, form, h2, iframe, input, label, p} = van.tags
    const page = van.state(null)
    const addressValue = van.state("")
    const status = van.state("")
    const busy = van.state(false)

    const withBaseUrl = (html, url) => {
        const baseUrl = url.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
        const baseElement = `<base href="${baseUrl}">`
        const existingBase = /<base\b[^>]*>/i
        const headTag = /<head\b[^>]*>/i
        const htmlTag = /<html\b[^>]*>/i

        if (existingBase.test(html)) return html.replace(existingBase, baseElement)
        if (headTag.test(html)) return html.replace(headTag, match => `${match}${baseElement}`)
        if (htmlTag.test(html)) return html.replace(htmlTag, match => `${match}<head>${baseElement}</head>`)
        return `<head>${baseElement}</head>${html}`
    }

    const openPage = async event => {
        event.preventDefault()
        if (busy.val) return
        const entered = addressValue.val.trim()
        const candidate = /^[a-z][a-z\d+.-]*:\/\//i.test(entered)
            ? entered
            : `https://${entered}`

        try {
            const parsed = new URL(candidate)
            if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
                throw new Error("Only HTTP and HTTPS sites can be opened.")
            }
        } catch {
            status.val = "Enter a valid website address."
            return
        }

        busy.val = true
        status.val = "Loading website..."
        try {
            const result = await fetchBrowserPage(candidate)
            page.val = {url: result.url, html: result.html}
            addressValue.val = result.url
            status.val = "Loaded in a restricted sandbox. Sites requiring third-party cookies may be limited."
        } catch (error) {
            page.val = null
            status.val = error.message
        } finally {
            busy.val = false
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
            button({type: "submit", disabled: () => busy.val}, () => busy.val ? "Loading..." : "Go"),
        ),
        p({class: "better-surf-status", role: "status", "aria-live": "polite"}, () => status.val),
        () => page.val
            ? iframe({
                class: "better-surf-page",
                title: "Website contents",
                srcdoc: withBaseUrl(page.val.html, page.val.url),
                sandbox: "allow-scripts allow-forms",
                referrerpolicy: "no-referrer",
                allowfullscreen: true,
            })
            : div({class: "better-surf-empty"}),
    )
}
