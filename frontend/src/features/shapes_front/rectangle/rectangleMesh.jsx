import React, { useRef } from 'react'
import { registerShape } from '../index'

const RectangleMesh = ({ geometry }) => {
    const meshRef = useRef()
    const { width, height, depth } = geometry.params
    const { color } = geometry.material

    return (
        <mesh ref={meshRef}>
            <boxGeometry args={[width, height, depth]} />
            <meshStandardMaterial color={color} />
        </mesh>
    )
}

registerShape('box', RectangleMesh)

export default RectangleMesh
