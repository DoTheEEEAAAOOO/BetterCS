import van from "../../node_modules/vanjs-core/src/van.js"
import {Tabs} from "../components/Tabs.js"

const {a, button, div, h1, h2, h3, header, main, p, section} = van.tags

export const Main = () => div(
  header(h1("BetterCS")),
  main(
    section(
      h2("Navigation"),
      Tabs({
        id: "main-tabs",
        label: "Navigation",
        tabs: [
          {
            label: "Overview",
            content: div(
              h3("Welcome to BetterCS"),
              p("A better experience for you using your computer, if you want control and power while keeping everything stable, secure, on cloud, and familiar for you if you are a SmartTV user. Looks pretty nostalgic too in my opinion!"),
              p("This is a work in progress, so please be patient and check back later for updates. If you have any questions or feedback, please contact me on GitHub as a GitHub issue, repo is"),
                a({href: "https://github.com/DoTheEEEAAAOOO/BetterCS"}, "on this link."),
            ),
          },
          {
            label: "VanJS",
            content: div(
              h3("VanJS"),
              p("A lightweight UI library built with vanilla JavaScript. This site uses it! Check it out, it is React but not sloppy, and it is fast!"),
              a({href: "https://vanjs.org/"}, "Visit VanJS"),
            ),
          },
          {
            label: "Download",
            content: div(
              h3("Download BetterCS"),
              p("Get any version of BetterCS here. It is made in Flask Python, so it is cross-platform and can run on any OS that supports Python. It is also open-source, so you can contribute to it if you want. If you cannot host it yourself, such as if you have a TV that can only run apps from the app store, you can download the latest version of BetterCS Prehoster, which currently support Android via APK, and Tizen via TPK."),
              button("Download BetterCS v1.0.Indev"),
              button("Download BetterCS Prehoster v1.0.Indev"),
            ),
          },
        ],
      }),
    ),
  ),
)

van.add(document.body, Main())