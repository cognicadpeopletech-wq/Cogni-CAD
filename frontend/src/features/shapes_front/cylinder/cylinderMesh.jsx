import React, { useRef } from 'react'
import { registerShape } from '../index'

const CylinderMesh = ({ geometry }) => {
    const meshRef = useRef()
    const { diameter, height } = geometry.params
    const { color } = geometry.material

    return (
        <mesh ref={meshRef} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[diameter / 2, diameter / 2, height, 32]} />
            <meshStandardMaterial color={color} />
        </mesh>
    )
}

registerShape('cylinder', CylinderMesh)

export default CylinderMesh
