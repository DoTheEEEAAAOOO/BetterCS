import van from "../../node_modules/vanjs-core/src/van.js"

const {a, button, div, h1, h2, h3, header, main, p, section, nav} = van.tags

export const Main = () => div(
    h1("BetterStore"),
    p("A application store for BetterCS, where you can find and download applications for your BetterCS device."),
    nav(
        a({href: "Sdk.html"}, "SDK"),
        a({href: "Apps.html"}, "Apps"),
        a({href: "About.html"}, "About"),
    ),
    main(
        section(
            p("Huge thank you for VanJS and NPM, without them this would be very hard to make, and I would not be able to make BetterCS and BetterStore as good as they are now. I am very grateful, and I hope when BetterCS gets popular and I get donations, I will be able to donate to VanJS and NPM to support them and their work. And also the following in this list:"),
            ul(
                li("VanJS"),
                li("NPM"),
                li("Node.js"),
                li("GitHub"),
                li("Git"),
                li("Visual Studio Code"),
                li("Flask"),
                li("Python"),
                li("Samsung"),
                li("GitHub Codespaces")
            ),
        ),
    ),
)

van.add(document.body, Main())