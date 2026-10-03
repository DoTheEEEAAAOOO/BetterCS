import {
    addFile,
    editFile,
    getTree,
    makeFolder,
    pushTree,
    removeFile,
    removeFolder,
    renameFile,
    renameFolder,
} from "../frontend/api.js"

export const BETTERCS_FILES_APP_VERSION = 2

export default function Files(van) {
    const {button, div, form, h2, input, label, option, p, pre, select, textarea} = van.tags
    const tree = van.state(null)
    const pendingChanges = van.state(0)
    const operation = van.state("add-file")
    const status = van.state("Loading repository tree...")
    const busy = van.state(false)

    const refreshTree = async () => {
        busy.val = true
        try {
            const result = await getTree()
            tree.val = result.tree
            pendingChanges.val = result.pendingChanges ?? 0
            status.val = `Loaded ${result.repo}.`
        } catch (error) {
            status.val = error.message
        } finally {
            busy.val = false
        }
    }

    const applyOperation = async event => {
        event.preventDefault()
        if (busy.val) return

        const formData = new FormData(event.currentTarget)
        const selectedOperation = formData.get("operation")?.toString() ?? operation.val
        const path = formData.get("path")?.toString().trim() ?? ""
        const newPath = formData.get("newPath")?.toString().trim() ?? ""
        const content = formData.get("content")?.toString() ?? ""

        busy.val = true
        status.val = "Updating tree..."
        try {
            let result
            switch (selectedOperation) {
                case "add-file":
                    result = await addFile(path, content)
                    break
                case "edit-file":
                    result = await editFile(path, content)
                    break
                case "remove-file":
                    result = await removeFile(path)
                    break
                case "make-folder":
                    result = await makeFolder(path)
                    break
                case "remove-folder":
                    result = await removeFolder(path)
                    break
                case "rename-file":
                    result = await renameFile(path, newPath)
                    break
                case "rename-folder":
                    result = await renameFolder(path, newPath)
                    break
                default:
                    throw new Error("Choose a valid file operation.")
            }

            tree.val = result.tree
            pendingChanges.val = result.pendingChanges ?? 0
            status.val = "Tree updated in memory. Push changes to save them to the repository."
            event.currentTarget.reset()
            operation.val = selectedOperation
        } catch (error) {
            status.val = error.message
        } finally {
            busy.val = false
        }
    }

    const saveTree = async () => {
        if (busy.val) return
        busy.val = true
        status.val = "Pushing tree to GitHub..."
        try {
            const result = await pushTree("Update BetterCS files")
            tree.val = result.tree
            pendingChanges.val = result.pendingChanges ?? 0
            status.val = result.message
        } catch (error) {
            status.val = error.message
        } finally {
            busy.val = false
        }
    }

    const showRenamePath = () => operation.val === "rename-file" || operation.val === "rename-folder"
    const showContent = () => operation.val === "add-file" || operation.val === "edit-file"

    const app = div({class: "files-app", "aria-busy": () => String(busy.val)},
        h2("Files"),
        div({class: "files-toolbar"},
            button({type: "button", onclick: refreshTree, disabled: () => busy.val}, "Refresh tree"),
            button({type: "button", onclick: saveTree, disabled: () => busy.val || pendingChanges.val === 0},
                () => `Push changes (${pendingChanges.val})`,
            ),
        ),
        form({class: "files-operation-form", onsubmit: applyOperation},
            label({for: "files-operation"}, "Operation"),
            select({
                id: "files-operation",
                name: "operation",
                value: () => operation.val,
                onchange: event => operation.val = event.currentTarget.value,
            },
                option({value: "add-file"}, "Add file"),
                option({value: "edit-file"}, "Edit file"),
                option({value: "remove-file"}, "Remove file"),
                option({value: "make-folder"}, "Make folder"),
                option({value: "remove-folder"}, "Remove folder"),
                option({value: "rename-file"}, "Rename file"),
                option({value: "rename-folder"}, "Rename folder"),
            ),
            label({for: "files-path"}, "Path"),
            input({
                id: "files-path",
                name: "path",
                type: "text",
                placeholder: "folder/file.txt",
                autocomplete: "off",
                required: true,
            }),
            () => showRenamePath()
                ? div(
                    label({for: "files-new-path"}, "New path"),
                    input({
                        id: "files-new-path",
                        name: "newPath",
                        type: "text",
                        placeholder: "folder/new-name.txt",
                        autocomplete: "off",
                        required: true,
                    }),
                )
                : div(),
            () => showContent()
                ? div(
                    label({for: "files-content"}, "File contents"),
                    textarea({
                        id: "files-content",
                        name: "content",
                        placeholder: "Enter UTF-8 text",
                        required: true,
                    }),
                )
                : div(),
            button({type: "submit", disabled: () => busy.val}, "Apply change"),
        ),
        p({class: "files-status", role: "status", "aria-live": "polite"}, () => status.val),
        pre({class: "files-tree-json", "aria-label": "Repository file tree JSON"},
            () => tree.val ? JSON.stringify(tree.val, null, 2) : "Loading file tree...",
        ),
    )

    refreshTree()
    return app
}
