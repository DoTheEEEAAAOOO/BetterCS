import van from "../../node_modules/vanjs-core/src/van.js"

const {button, div} = van.tags
let nextTabsId = 0

export const Tabs = ({id, label = "Tabs", tabs, initialTab = 0}) => {
  if (!Array.isArray(tabs) || tabs.length === 0) {
    throw new TypeError("Tabs requires at least one tab.")
  }

  const tabsId = id ?? `tabs-${++nextTabsId}`
  const startIndex = Number.isInteger(initialTab)
    ? Math.min(Math.max(initialTab, 0), tabs.length - 1)
    : 0
  const activeTab = van.state(startIndex)

  const activateTab = (index, moveFocus = false) => {
    activeTab.val = index
    if (moveFocus) document.getElementById(`${tabsId}-tab-${index}`)?.focus()
  }

  const handleKeydown = (event, index) => {
    let nextIndex

    switch (event.key) {
      case "ArrowRight":
        nextIndex = (index + 1) % tabs.length
        break
      case "ArrowLeft":
        nextIndex = (index - 1 + tabs.length) % tabs.length
        break
      case "Home":
        nextIndex = 0
        break
      case "End":
        nextIndex = tabs.length - 1
        break
      default:
        return
    }

    event.preventDefault()
    activateTab(nextIndex, true)
  }

  return div({class: "tabs"},
    div({
      class: "tabs-list",
      role: "tablist",
      "aria-label": label,
    },
    ...tabs.map((tab, index) => button({
      id: `${tabsId}-tab-${index}`,
      type: "button",
      role: "tab",
      "aria-controls": `${tabsId}-panel-${index}`,
      "aria-selected": () => activeTab.val === index,
      tabindex: () => activeTab.val === index ? 0 : -1,
      onclick: () => activateTab(index),
      onkeydown: event => handleKeydown(event, index),
      class: "tabs-trigger",
    }, tab.label)),
    ),
    ...tabs.map((tab, index) => div({
      id: `${tabsId}-panel-${index}`,
      class: "tabs-panel",
      role: "tabpanel",
      "aria-labelledby": `${tabsId}-tab-${index}`,
      tabindex: 0,
      hidden: () => activeTab.val !== index,
    }, tab.content)),
  )
}