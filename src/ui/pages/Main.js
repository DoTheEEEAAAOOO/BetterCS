import van from "../../node_modules/vanjs-core/src/van.js"
import {Tabs} from "../components/Tabs.js"

const {a, div, h1, h2, h3, header, main, p, section} = van.tags

export const Main = () => div(
  header(h1("BetterCS")),
  main(
    section(
      h2("Workspace"),
      Tabs({
        id: "workspace-tabs",
        label: "Workspace sections",
        tabs: [
          {
            label: "Overview",
            content: div(
              h3("👋 Hello, World"),
              p("Welcome to BetterCS."),
            ),
          },
          {
            label: "VanJS",
            content: div(
              h3("🍦 VanJS"),
              p("A lightweight UI library built with vanilla JavaScript."),
              a({href: "https://vanjs.org/"}, "Visit VanJS"),
            ),
          },
          {
            label: "About",
            content: div(
              h3("BetterCS"),
              p("A better experience."),
            ),
          },
        ],
      }),
    ),
  ),
)

van.add(document.body, Main())