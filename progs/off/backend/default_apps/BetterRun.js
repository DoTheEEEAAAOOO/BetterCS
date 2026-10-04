export default function BetterRun(van) {
    const {button, div, h2, p, textarea} = van.tags
    
    return div({class: "bettercs-app bettercs-better-run"},
        h2("BetterRun"),
        p("A playground for running VanJS code as BetterCS apps via SDK. This app is still under development and may not be fully functional."),
        textarea({class: "bettercs-better-run-editor", placeholder: "Enter your VanJS code here..."}),
        button({class: "bettercs-better-run-button", onclick: () => {
            const code = document.querySelector(".bettercs-better-run-editor").value
            try {
                const func = new Function("van", code)
                func(van)
            } catch (error) {
                alert(`Error executing code: ${error.message}`)
            }
        }}, "Run Code"),
    )
}