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
        Tabs({
            id: "welcome-tabs",
            label: "Welcome Tabs",
            tabs: [
                {
                    label: "The Experience",
                    content: div(
                        h1("The Experience"),
                        p("BetterCS is a better experience for you using your computer, if you want control and power while keeping everything stable, secure, on cloud, and familiar for you if you are a SmartTV user. Looks pretty nostalgic too in my opinion!"),
                        p("It might look pretty tough if you never used a SmartTV, Tablet, Phone, or Computer before, but it is actually pretty simple to use. It is organized like Tizen, ensuring you have the app content, a pop-out menu bar, and a home screen that is not shoved into your face at first."),
                    ),
                }
            ]
        })
    ),
)

van.add(document.body, Main())