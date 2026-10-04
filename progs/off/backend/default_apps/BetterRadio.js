import {getRadioStations} from "../frontend/api.js"

export default function BetterRadio(van) {
    const {audio, button, div, h2, input, label, p} = van.tags
    const countryCode = van.state("")
    const countryName = van.state("")
    const stations = van.state([])
    const currentStation = van.state("")
    const status = van.state("Detecting your country...")
    const busy = van.state(false)
    const player = audio({
        class: "better-radio-player",
        controls: true,
        preload: "none",
        onplaying: () => status.val = `Playing ${currentStation.val}.`,
        onerror: () => status.val = "This station's stream could not be played.",
    })

    const loadStations = async () => {
        const code = countryCode.val.trim().toUpperCase()
        if (!/^[A-Z]{2}$/.test(code)) {
            status.val = "Enter a two-letter country code."
            return
        }

        countryCode.val = code
        busy.val = true
        status.val = `Loading stations for ${code}...`
        try {
            const result = await getRadioStations(code)
            countryName.val = result.country || code
            stations.val = result.stations
            status.val = result.stations.length
                ? `${result.stations.length} stations found in ${countryName.val}.`
                : `No stations found in ${countryName.val}.`
        } catch (error) {
            stations.val = []
            status.val = error.message
        } finally {
            busy.val = false
        }
    }

    const detectCountry = async () => {
        try {
            const response = await fetch("https://ipapi.co/json/", {
                headers: {Accept: "application/json"},
            })
            if (!response.ok) throw new Error("Country detection is unavailable.")
            const location = await response.json()
            if (!/^[A-Za-z]{2}$/.test(location.country_code ?? "")) {
                throw new Error("Country detection returned no country code.")
            }
            countryCode.val = location.country_code.toUpperCase()
            countryName.val = location.country_name ?? countryCode.val
            await loadStations()
        } catch {
            status.val = "Enter your two-letter country code to find local stations."
        }
    }

    const playStation = station => {
        const streamUrl = station.streamUrl
        if (!/^https?:\/\//i.test(streamUrl)) {
            status.val = "This station does not have a supported stream URL."
            return
        }

        currentStation.val = station.name
        status.val = `Connecting to ${station.name}...`
        player.src = streamUrl
        player.load()
        const playback = player.play()
        if (playback?.catch) {
            playback.catch(() => {
                status.val = "Playback was blocked or this station's stream is unavailable."
            })
        }
    }

    const app = div({class: "better-radio-app"},
        h2("BetterRadio"),
        div({class: "better-radio-location"},
            label({for: "better-radio-country"}, "Country"),
            input({
                id: "better-radio-country",
                type: "text",
                value: () => countryCode.val,
                maxlength: 2,
                placeholder: "US",
                autocomplete: "country",
                oninput: event => countryCode.val = event.currentTarget.value,
            }),
            button({type: "button", onclick: loadStations, disabled: () => busy.val},
                () => busy.val ? "Loading..." : "Find stations",
            ),
        ),
        p({class: "better-radio-status", role: "status", "aria-live": "polite"}, () => status.val),
        player,
        div({class: "better-radio-stations", role: "list", "aria-label": "Radio stations"},
            () => div({class: "better-radio-station-list"},
                ...stations.val.map((station, index) => button({
                    type: "button",
                    class: "better-radio-station",
                    role: "listitem",
                    "aria-current": () => currentStation.val === station.name ? "true" : "false",
                    onclick: () => playStation(station),
                },
                    p({class: "better-radio-station-name"}, station.name || `Station ${index + 1}`),
                    p({class: "better-radio-station-meta"},
                        [station.state, station.country, station.codec, station.bitrate ? `${station.bitrate} kbps` : ""]
                            .filter(Boolean)
                            .join(" · "),
                    ),
                )),
            ),
        ),
    )

    detectCountry()
    return app
}
