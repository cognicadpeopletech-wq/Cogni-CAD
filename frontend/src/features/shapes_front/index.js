// Registry maps shape type -> React Component for rendering
// And potentially other metadata

const registry = {}

export const registerShape = (type, component) => {
    registry[type] = component
}

export const getShapeComponent = (type) => {
    return registry[type] || null
}
