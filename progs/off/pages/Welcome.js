import van from "https://cdn.jsdelivr.net/npm/vanjs-core@1.6.1/src/van.js"
import {Notif} from "../components/Notif.js"

const {div, h1, header, main} = van.tags

const Main = () => div(
    header(h1("Welcome to BetterCS")),
    main(
        Notif(
            "Thank you for installing BetterCS!",
            "It is really nice for me (the owner) to see that you are using BetterCS. I hope you enjoy it! It makes me really happy to see someone use my project.",
        ),
    ),
)

van.add(document.body, Main())