import van from "https://cdn.jsdelivr.net/npm/vanjs-core@1.6.1/src/van.js"
import {Tabs} from "../components/Tabs.js"


const {h1, h2, h3, h4, h5, h6, p, div, dialog, Tabs} = van.tags

const Main() => div(
    h1("Welcome to BetterCS"),
    dialog("Thank you for installing BetterCS!", "It is really nice for me (the owner) to see that you are using BetterCS. I hope you enjoy it! It makes me really happy to see someone use my project."),
)