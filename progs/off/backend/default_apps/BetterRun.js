export default function BetterRun(van) {
    const {button, div, h2, p, textarea} = van.tags
    const initialCode = `const {div, h2, p} = van.tags
return div(
    h2("Hello from BetterRun"),
    p("Edit this component and run it again."),
)`
    const code = van.state(initialCode)
    const status = van.state("")
    const running = van.state(false)
    const preview = div({class: "better-run-preview", "aria-live": "polite"})

    const runCode = () => {
        if (running.val) return
        running.val = true
        status.val = ""

        try {
            const result = new Function("van", `"use strict";\n${code.val}`)(van)
            if (!(result instanceof Node)) {
                throw new TypeError("Return a VanJS element from your code.")
            }

            while (preview.firstChild) preview.removeChild(preview.firstChild)
            van.add(preview, result)
            status.val = "Preview updated."
        } catch (error) {
            status.val = error instanceof Error ? error.message : String(error)
        } finally {
            running.val = false
        }
    }

    return div({class: "bettercs-app bettercs-better-run"},
        h2("BetterRun"),
        p("Write a VanJS component that returns an element. Run it to update the preview."),
        textarea({
            class: "better-run-editor",
            "aria-label": "VanJS component source",
            spellcheck: false,
            value: () => code.val,
            oninput: event => code.val = event.currentTarget.value,
            onkeydown: event => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault()
                    runCode()
                }
            },
        }),
        button({type: "button", onclick: runCode, disabled: () => running.val},
            () => running.val ? "Running..." : "Run code",
        ),
        p({class: "better-run-status", role: "status", "aria-live": "polite"}, () => status.val),
        preview,
    )
}