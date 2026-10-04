import van from "../../node_modules/vanjs-core/src/van.js"

const {a, button, div, h1, h2, h3, header, li, main, nav, p, section, ul} = van.tags

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
        section(
            p("Placeholders for app listings")
        ),
    ),
)

van.add(document.body, Main())