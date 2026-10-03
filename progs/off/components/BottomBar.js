import van from "../lib/van.js"

const {button, div} = van.tags
let activeBottomBar = null
let keyHandlerInstalled = false

const installKeyHandler = () => {
  if (keyHandlerInstalled || typeof window === "undefined") return

  window.addEventListener("keydown", event => {
    if (event.key !== "Fn" && event.code !== "Fn" && event.key !== "F6") return

    const target = event.target
    const isEditing = target instanceof HTMLElement && (
      target.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
    )
    if (isEditing && event.key !== "Fn" && event.code !== "Fn") return

    event.preventDefault()
    activeBottomBar?.toggle()
  })

  keyHandlerInstalled = true
}

export const BottomBar = ({
  Menu = [],
  ListBar = [],
  id = "bettercs-bottom-bar",
  label = "BetterCS bottom bar",
  onListBarChange = () => {},
} = {}) => {
  const menus = Array.isArray(Menu) ? Menu.map((menu, index) => ({
    id: String(menu.id ?? `menu-${index}`),
    label: String(menu.label ?? `Menu ${index + 1}`),
    items: Array.isArray(menu.items) ? menu.items : [],
  })) : []
  const initialItems = Array.isArray(ListBar) ? ListBar.map((item, index) => (
    typeof item === "string"
      ? {id: `item-${index}`, label: item}
      : {...item, id: String(item.id ?? `item-${index}`), label: String(item.label ?? `Item ${index + 1}`)}
  )) : []

  const isOpen = van.state(false)
  const activeMenu = van.state(-1)
  const menuExpanded = van.state(false)
  const listItems = van.state(initialItems)

  const focusMenuButton = index => {
    requestAnimationFrame(() => document.getElementById(`${id}-menu-${index}`)?.focus())
  }

  const focusMenuItem = (menuIndex, itemIndex = 0) => {
    requestAnimationFrame(() => document.getElementById(`${id}-menu-item-${menuIndex}-${itemIndex}`)?.focus())
  }

  const focusListItem = index => {
    requestAnimationFrame(() => document.getElementById(`${id}-list-item-${index}`)?.focus())
  }

  const closeMenu = () => {
    menuExpanded.val = false
    if (activeMenu.val >= 0) focusMenuButton(activeMenu.val)
  }

  const closeBar = () => {
    isOpen.val = false
    menuExpanded.val = false
    requestAnimationFrame(() => document.getElementById(`${id}-launcher`)?.focus())
  }

  const openBar = () => {
    isOpen.val = true
    activeMenu.val = menus.length ? 0 : -1
    menuExpanded.val = false
    requestAnimationFrame(() => {
      const focusTarget = menus.length
        ? `${id}-menu-0`
        : initialItems.length ? `${id}-list-item-0` : `${id}-close`
      document.getElementById(focusTarget)?.focus()
    })
  }

  const toggle = () => {
    if (isOpen.val) {
      closeBar()
    } else {
      openBar()
    }
  }

  activeBottomBar = {toggle}
  installKeyHandler()

  const showMenu = (index, focusItem = false) => {
    if (index < 0 || index >= menus.length) return
    activeMenu.val = index
    menuExpanded.val = true
    if (focusItem && menus[index].items.length) focusMenuItem(index)
  }

  const selectMenu = index => {
    if (activeMenu.val === index && menuExpanded.val) {
      closeMenu()
      return
    }
    showMenu(index)
  }

  const selectMenuItem = item => {
    const action = item.onSelect ?? item.action
    const selectedMenu = activeMenu.val
    menuExpanded.val = false
    focusMenuButton(selectedMenu)
    if (typeof action === "function") action()
  }

  const moveListItem = (index, offset) => {
    const destination = index + offset
    const currentItems = listItems.val
    if (destination < 0 || destination >= currentItems.length) return

    const nextItems = [...currentItems]
    ;[nextItems[index], nextItems[destination]] = [nextItems[destination], nextItems[index]]
    listItems.val = nextItems
    onListBarChange([...nextItems])
    focusListItem(destination)
  }

  const handleMenuKeydown = (event, index) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault()
      const offset = event.key === "ArrowRight" ? 1 : -1
      const nextIndex = (index + offset + menus.length) % menus.length
      activeMenu.val = nextIndex
      focusMenuButton(nextIndex)
      if (menuExpanded.val && menus[nextIndex].items.length) focusMenuItem(nextIndex)
      return
    }

    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      if (!menus[index].items.length) return
      event.preventDefault()
      showMenu(index, true)
    }
  }

  const handleMenuItemKeydown = (event, menuIndex, itemIndex) => {
    const items = menus[menuIndex].items
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault()
      const offset = event.key === "ArrowDown" ? 1 : -1
      const nextIndex = (itemIndex + offset + items.length) % items.length
      focusMenuItem(menuIndex, nextIndex)
    } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault()
      const offset = event.key === "ArrowRight" ? 1 : -1
      const nextMenu = (menuIndex + offset + menus.length) % menus.length
      activeMenu.val = nextMenu
      menuExpanded.val = true
      focusMenuButton(nextMenu)
      if (menus[nextMenu].items.length) focusMenuItem(nextMenu)
    }
  }

  const handleListKeydown = (event, index) => {
    if ((event.key === "ArrowLeft" || event.key === "ArrowRight") && event.shiftKey) {
      event.preventDefault()
      moveListItem(index, event.key === "ArrowRight" ? 1 : -1)
      return
    }

    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault()
      const offset = event.key === "ArrowRight" ? 1 : -1
      const nextIndex = (index + offset + listItems.val.length) % listItems.val.length
      focusListItem(nextIndex)
    }
  }

  const handleBarKeydown = event => {
    if (event.key === "Escape") {
      event.preventDefault()
      if (menuExpanded.val) closeMenu()
      else closeBar()
    }
  }

  return div({class: "bottom-bar-component"},
    button({
      id: `${id}-launcher`,
      type: "button",
      class: "bottom-bar-launcher",
      "aria-label": "Open quick menu",
      "aria-expanded": () => String(isOpen.val),
      "aria-keyshortcuts": "F6",
      title: "Open quick menu (Fn or F6)",
      hidden: () => isOpen.val,
      onclick: toggle,
    }, "Menu"),
    div({
      id,
      class: () => `bottom-bar${isOpen.val ? " is-open" : ""}`,
      role: "region",
      "aria-label": label,
      "aria-hidden": () => String(!isOpen.val),
      inert: () => !isOpen.val,
      onkeydown: handleBarKeydown,
    },
      div({class: "bottom-bar-main"},
        div({class: "bottom-bar-menu-area"},
          div({class: "bottom-bar-menu-list", role: "menubar", "aria-label": "Menus"},
            ...menus.map((menu, index) => button({
              id: `${id}-menu-${index}`,
              type: "button",
              class: () => `bottom-bar-menu-trigger${activeMenu.val === index ? " is-active" : ""}`,
              role: "menuitem",
              "aria-haspopup": "menu",
              "aria-expanded": () => String(activeMenu.val === index && menuExpanded.val),
              tabindex: () => activeMenu.val === index ? 0 : -1,
              onclick: () => selectMenu(index),
              onkeydown: event => handleMenuKeydown(event, index),
            }, menu.label)),
          ),
          div({
            class: "bottom-bar-menu-popup",
            role: "menu",
            "aria-label": () => menus[activeMenu.val]?.label ?? "Menu items",
            hidden: () => !isOpen.val || !menuExpanded.val || !menus[activeMenu.val]?.items.length,
          }, () => {
            const menuIndex = activeMenu.val
            const items = menus[menuIndex]?.items ?? []
            return div({class: "bottom-bar-menu-items"},
              ...items.map((item, index) => button({
                id: `${id}-menu-item-${menuIndex}-${index}`,
                type: "button",
                class: "bottom-bar-menu-item",
                role: "menuitem",
                tabindex: -1,
                onclick: () => selectMenuItem(item),
                onkeydown: event => handleMenuItemKeydown(event, menuIndex, index),
              }, item.label ?? `Item ${index + 1}`)),
            )
          },
          ),
        ),
        div({class: "bottom-bar-list-area", role: "toolbar", "aria-label": "Quick actions"},
          () => div({class: "bottom-bar-list-items"},
            ...listItems.val.map((item, index) => div({
              class: "bottom-bar-list-item",
              key: item.id,
            },
              button({
                id: `${id}-list-item-${index}`,
                type: "button",
                class: "bottom-bar-action",
                title: item.label,
                onclick: () => (item.onClick ?? item.action)?.(),
                onkeydown: event => handleListKeydown(event, index),
              }, item.label),
              button({
                type: "button",
                class: "bottom-bar-reorder move-left",
                "aria-label": `Move ${item.label} left`,
                title: "Move left",
                disabled: index === 0,
                onclick: () => moveListItem(index, -1),
              }),
              button({
                type: "button",
                class: "bottom-bar-reorder move-right",
                "aria-label": `Move ${item.label} right`,
                title: "Move right",
                disabled: index === listItems.val.length - 1,
                onclick: () => moveListItem(index, 1),
              }),
            )),
          ),
        ),
        button({
          id: `${id}-close`,
          type: "button",
          class: "bottom-bar-close",
          "aria-label": "Close quick menu",
          title: "Close quick menu",
          onclick: closeBar,
        }, "Close"),
      ),
    ),
  )
}