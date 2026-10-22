import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { BuildingModel, BuildingVolume, FacadeSide, FacadeStyle } from './building-model'
import { tokens } from '../theme'

interface Controller { update: (model: BuildingModel) => void; reset: () => void; dispose: () => void }
export interface BuildingSceneHandle { reset: () => void }

const DEG = Math.PI / 180
const TAU = Math.PI * 2
const Y_AXIS = new THREE.Vector3(0, 1, 0)

interface SideSpec { name: FacadeSide; axis: 'x' | 'z'; sign: 1 | -1; rotationY: number }
const SIDES: readonly SideSpec[] = [
  { name: '南', axis: 'z', sign: 1, rotationY: 0 },
  { name: '北', axis: 'z', sign: -1, rotationY: Math.PI },
  { name: '东', axis: 'x', sign: 1, rotationY: Math.PI / 2 },
  { name: '西', axis: 'x', sign: -1, rotationY: -Math.PI / 2 },
]

type WindowStyle = 'simple' | 'vertical' | 'cross' | 'grid' | 'module' | 'ribbon'
const WINDOW_STYLE: Record<FacadeStyle, WindowStyle> = {
  wall: 'vertical', hybrid: 'cross', frame: 'ribbon', modular: 'vertical', neutral: 'simple',
}

/** 以单位盒合并出窗框：外框 + 竖/横分格 + 深色底板，玻璃单独一片，形成窗洞进深。 */
function createWindowFrameGeometry(style: WindowStyle): THREE.BufferGeometry {
  const columns = style === 'grid' ? 3 : style === 'ribbon' ? 4 : style === 'simple' ? 1 : 2
  const rows = style === 'grid' || style === 'cross' || style === 'module' || style === 'ribbon' ? 2 : 1
  const bar = style === 'module' ? .058 : style === 'grid' ? .03 : style === 'ribbon' ? .026 : .05
  const thin = style === 'grid' || style === 'module' ? bar * .74 : style === 'ribbon' ? .018 : bar * .86
  const parts: { w: number; h: number; d: number; x: number; y: number; z: number }[] = [
    // 底板比玻璃大，玻璃收进框内，远看有窗套阴影而不是一块贴纸。
    { w: 1, h: 1, d: .006, x: 0, y: 0, z: -.006 },
    { w: 1, h: bar, d: .03, x: 0, y: .5 - bar / 2, z: .01 },
    { w: 1, h: bar, d: .042, x: 0, y: -.5 + bar / 2, z: .016 },
    { w: bar, h: 1 - bar * 2, d: .03, x: -.5 + bar / 2, y: 0, z: .01 },
    { w: bar, h: 1 - bar * 2, d: .03, x: .5 - bar / 2, y: 0, z: .01 },
  ]
  for (let column = 1; column < columns; column++) parts.push({
    w: thin, h: 1 - bar * 2, d: .018, x: -.5 + column / columns, y: 0, z: .006,
  })
  for (let row = 1; row < rows; row++) parts.push({
    w: 1 - bar * 2, h: thin, d: .018, x: 0, y: -.5 + row / rows, z: .006,
  })
  const geometries = parts.map(part => {
    const geometry = new THREE.BoxGeometry(part.w, part.h, part.d)
    geometry.translate(part.x, part.y, part.z)
    return geometry
  })
  const merged = mergeGeometries(geometries, false) ?? new THREE.BufferGeometry()
  for (const geometry of geometries) geometry.dispose()
  return merged
}

/** 无外部 HDR：用渐变穹顶和两块发光板生成 PMREM 环境，玻璃有可读的天空/柔光反射。 */
function createStudioEnvironment(renderer: THREE.WebGLRenderer): THREE.WebGLRenderTarget {
  const envScene = new THREE.Scene()
  const domeGeometry = new THREE.SphereGeometry(10, 32, 16)
  const position = domeGeometry.attributes.position
  const colors = new Float32Array(position.count * 3)
  const top = new THREE.Color(tokens.scene.skyTop), horizon = new THREE.Color(tokens.scene.skyHorizon), ground = new THREE.Color(tokens.scene.skyGround)
  const color = new THREE.Color()
  for (let index = 0; index < position.count; index++) {
    const height = THREE.MathUtils.clamp(position.getY(index) / 10 * .5 + .5, 0, 1)
    if (height > .5) color.lerpColors(horizon, top, (height - .5) * 2)
    else color.lerpColors(ground, horizon, height * 2)
    colors[index * 3] = color.r; colors[index * 3 + 1] = color.g; colors[index * 3 + 2] = color.b
  }
  domeGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  const dome = new THREE.Mesh(domeGeometry, new THREE.MeshBasicMaterial({ side: THREE.BackSide, vertexColors: true }))
  envScene.add(dome)
  const addPanel = (width: number, height: number, rgb: [number, number, number], x: number, y: number, z: number) => {
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(width, height),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(...rgb), side: THREE.DoubleSide, toneMapped: false }))
    panel.position.set(x, y, z)
    panel.lookAt(0, 0, 0)
    envScene.add(panel)
  }
  // 左前上方暖阳、右侧冷天光、正上方高光，给玻璃和金属提供方向性反射。
  addPanel(4.8, 3.2, [3.1, 2.85, 2.35], -4.5, 6, 4.8)
  addPanel(3.4, 2.6, [.62, .88, .9], 5.5, 3.4, -3.2)
  addPanel(2.2, 1.8, [1.9, 1.85, 1.7], 1.2, 6.2, 1.8)
  const generator = new THREE.PMREMGenerator(renderer)
  const target = generator.fromScene(envScene, .02)
  generator.dispose()
  envScene.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return
    object.geometry.dispose()
    const material = object.material
    if (Array.isArray(material)) material.forEach(item => item.dispose())
    else material.dispose()
  })
  return target
}

/** 接触阴影和底板投影共用的柔边圆斑，不额外下载贴图。 */
function createShadowTexture(): THREE.CanvasTexture {
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = size; canvas.height = size
  const context = canvas.getContext('2d')
  if (context) {
    const gradient = context.createRadialGradient(size / 2, size / 2, 2, size / 2, size / 2, size / 2)
    gradient.addColorStop(0, 'rgba(255,255,255,.92)')
    gradient.addColorStop(.52, 'rgba(255,255,255,.34)')
    gradient.addColorStop(1, 'rgba(255,255,255,0)')
    context.fillStyle = gradient
    context.fillRect(0, 0, size, size)
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

/** 可见时缓慢环绕；拖动、减少动态效果与不可见状态下暂停自动旋转。 */
function createScene(host: HTMLDivElement, onUnavailable: () => void, onReady: () => void): Controller {
  let disposed = false, frame = 0
  let allocatedRenderer: THREE.WebGLRenderer | undefined
  let environmentTarget: THREE.WebGLRenderTarget | undefined
  const cleanups: (() => void)[] = []
  const resources = new Set<THREE.BufferGeometry | THREE.Material>()
  const keep = <T extends THREE.BufferGeometry | THREE.Material>(resource: T): T => { resources.add(resource); return resource }
  const dispose = () => {
    if (disposed) return
    disposed = true
    cancelAnimationFrame(frame)
    // 一项释放失败也继续回收后续资源，包括未完成的初始化。
    for (const cleanup of cleanups.reverse()) { try { cleanup() } catch { /* 继续清理 */ } }
    const textures = new Set<THREE.Texture>()
    for (const resource of resources) {
      if (resource instanceof THREE.Material) for (const value of Object.values(resource)) if (value instanceof THREE.Texture) textures.add(value)
    }
    for (const texture of textures) { try { texture.dispose() } catch { /* 继续清理 */ } }
    for (const resource of resources) { try { resource.dispose() } catch { /* 继续清理 */ } }
    resources.clear()
    try { environmentTarget?.dispose() } catch { /* 仍要释放上下文 */ }
    try { allocatedRenderer?.dispose() } catch { /* 仍要释放上下文 */ }
    try { allocatedRenderer?.forceContextLoss() } catch { /* 上下文可能已经丢失 */ }
    allocatedRenderer = undefined
  }
  try {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' })
  allocatedRenderer = renderer
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, innerWidth < 768 ? 1.3 : 1.8))
  renderer.setClearColor(0x000000, 0)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = .98
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.shadowMap.autoUpdate = false
  renderer.shadowMap.needsUpdate = true
  const canvas = renderer.domElement
  canvas.tabIndex = 0
  canvas.setAttribute('role', 'img')
  canvas.setAttribute('aria-label', '参数驱动建筑体量。左右拖动或方向键旋转，Home 复位。')
  host.appendChild(canvas)
  cleanups.push(() => canvas.remove())
  const scene = new THREE.Scene()
  cleanups.push(() => {
    scene.traverse(object => {
      if (object instanceof THREE.InstancedMesh) object.dispose()
      else if (object instanceof THREE.Mesh && object.userData.ownedGeometry) object.geometry.dispose()
    })
    scene.clear()
  })
  try { environmentTarget = createStudioEnvironment(renderer) } catch { environmentTarget = undefined }
  if (environmentTarget) {
    scene.environment = environmentTarget.texture
    scene.environmentIntensity = .52
    cleanups.push(() => { scene.environment = null; environmentTarget?.dispose(); environmentTarget = undefined })
  }

  const camera = new THREE.PerspectiveCamera(32, 1, .1, 100)
  camera.up.set(0, 1, 0)
  const focus = new THREE.Vector3(0, 1.15, 0)
  let fitRadius = 2.2
  let yaw = 0, targetYaw = yaw, pitch = 0, targetPitch = 0
  let pointer: { id: number; x: number; y: number; yaw: number; pitch: number } | undefined
  let lastTick = 0, lastDraw = 0, pauseUntil = 0
  let visible = true, ready = false, failed = false
  let resumeTimer: ReturnType<typeof setTimeout> | undefined
  cleanups.push(() => clearTimeout(resumeTimer))
  const reduce = matchMedia('(prefers-reduced-motion: reduce)')

  const world = new THREE.Group()
  scene.add(world)
  let volumes = new THREE.Group()
  let site = new THREE.Group()
  world.add(volumes); world.add(site)

  const hemisphere = new THREE.HemisphereLight(0xf7f1e2, 0xc9c2b3, .15)
  scene.add(hemisphere)
  const sun = new THREE.DirectionalLight(0xfff0d6, 4.8)
  sun.position.set(-6, 11, 7)
  sun.castShadow = true
  const shadowSize = innerWidth < 900 ? 1024 : 2048
  sun.shadow.mapSize.set(shadowSize, shadowSize)
  sun.shadow.camera.near = 1
  sun.shadow.camera.far = 42
  sun.shadow.bias = -.0004
  sun.shadow.normalBias = .012
  sun.shadow.radius = 2.5
  scene.add(sun); scene.add(sun.target)
  cleanups.push(() => sun.shadow.dispose())
  const fill = new THREE.DirectionalLight(0xf4ede0, .55)
  fill.position.set(7, 4, 8)
  scene.add(fill)
  const rim = new THREE.DirectionalLight(0xd8ece6, .35)
  rim.position.set(6, 5, -7)
  scene.add(rim)

  // ---- 共享几何体与材质：一次创建，所有楼栋复用 ----
  const boxGeometry = keep(new THREE.BoxGeometry(1, 1, 1))
  const roundedGeometry = keep(new RoundedBoxGeometry(1, 1, 1, 3, .035))
  const boardGeometry = keep(new RoundedBoxGeometry(1, 1, 1, 4, .05))
  const glassGeometry = keep(new THREE.BoxGeometry(1, 1, .01))
  const contactGeometry = keep(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2))
  const groundShadowMaterial = keep(new THREE.ShadowMaterial({ color: tokens.scene.shadow, opacity: .2, depthWrite: false }))
  groundShadowMaterial.toneMapped = false
  // 展台之外的“桌面”只接收阴影，让模型长阴影落到页面底纹上。
  const groundShadow = new THREE.Mesh(contactGeometry, groundShadowMaterial)
  groundShadow.scale.set(20, 1, 18)
  groundShadow.position.y = -.22
  groundShadow.receiveShadow = true
  scene.add(groundShadow)
  const trunkGeometry = keep(new THREE.CylinderGeometry(.0055, .009, .1, 6).translate(0, .05, 0))
  const foliageGeometry = keep(new THREE.IcosahedronGeometry(.078, 0))
  const windowFrames = new Map<WindowStyle, THREE.BufferGeometry>()
  for (const style of new Set(Object.values(WINDOW_STYLE))) windowFrames.set(style, keep(createWindowFrameGeometry(style)))

  const bodyMaterials: Record<FacadeStyle, THREE.MeshStandardMaterial> = {
    wall: keep(new THREE.MeshStandardMaterial({ color: tokens.scene.body, roughness: .78 })),
    hybrid: keep(new THREE.MeshStandardMaterial({ color: tokens.scene.bodyCool, roughness: .76 })),
    frame: keep(new THREE.MeshStandardMaterial({ color: tokens.scene.frameBody, roughness: .76 })),
    modular: keep(new THREE.MeshStandardMaterial({ color: tokens.scene.bodyWarm, roughness: .8 })),
    neutral: keep(new THREE.MeshStandardMaterial({ color: tokens.scene.neutralBody, roughness: .8 })),
  }
  const stoneMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.stone, roughness: .84 }))
  const stoneEdgeMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.stoneEdge, roughness: .82 }))
  const paperMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.paper, roughness: .68 }))
  const roofMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.rooftop, roughness: .78 }))
  const roofDeckMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.roofDeck, roughness: .92 }))
  const metalDarkMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.metalDark, roughness: .36, metalness: .58 }))
  const metalMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.metal, roughness: .42, metalness: .5 }))
  const louverMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.louver, roughness: .62, metalness: .28 }))
  const bandMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.band, roughness: .88 }))
  const glassMaterial = keep(new THREE.MeshPhysicalMaterial({
    color: tokens.scene.glass, roughness: .06, metalness: .4, clearcoat: 1, clearcoatRoughness: .04,
    envMapIntensity: 3.2, ior: 1.5,
  }))
  const glassModularMaterial = keep(new THREE.MeshPhysicalMaterial({
    color: tokens.scene.glassModular, roughness: .07, metalness: .2, clearcoat: 1, clearcoatRoughness: .05,
    envMapIntensity: 2.8, ior: 1.5,
  }))
  const glassFrameMaterial = keep(new THREE.MeshPhysicalMaterial({
    color: tokens.scene.glassFrame, roughness: .07, metalness: .24, clearcoat: 1, clearcoatRoughness: .05,
    envMapIntensity: 2.9, ior: 1.5,
  }))
  const glassByFacade: Record<FacadeStyle, THREE.MeshPhysicalMaterial> = {
    wall: glassMaterial, hybrid: glassMaterial, frame: glassFrameMaterial, modular: glassModularMaterial, neutral: glassMaterial,
  }
  const glassDeepMaterial = keep(new THREE.MeshPhysicalMaterial({
    color: tokens.scene.glassDark, roughness: .06, metalness: .38, clearcoat: .9, clearcoatRoughness: .06,
    envMapIntensity: 1.8, ior: 1.5,
  }))
  const plantMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.plant, roughness: .92, flatShading: true }))
  const treeMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.surface, roughness: .9, flatShading: true }))
  const trunkMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.trunk, roughness: .95 }))
  const boardMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.board, roughness: .92 }))
  const terraceMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.terrace, roughness: .9 }))
  const pathMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.paper, roughness: .86 }))
  const shadowTexture = createShadowTexture()
  const contactMaterial = keep(new THREE.MeshBasicMaterial({
    map: shadowTexture, color: tokens.scene.shadow, transparent: true, opacity: .34,
    depthWrite: false, toneMapped: false,
  }))
  const boardShadowMaterial = keep(new THREE.MeshBasicMaterial({
    map: shadowTexture, color: tokens.scene.shadow, transparent: true, opacity: .2,
    depthWrite: false, toneMapped: false,
  }))
  contactMaterial.polygonOffset = true; contactMaterial.polygonOffsetFactor = -1
  boardShadowMaterial.polygonOffset = true

  const tempMatrix = new THREE.Matrix4()
  const tempQuaternion = new THREE.Quaternion()
  const tempPosition = new THREE.Vector3()
  const tempScale = new THREE.Vector3()
  // 框剪方案保留实墙肢：每侧隔几跨就有一道通高剪力墙，和整面开窗的框架方案拉开差别。
  const hybridSolidBays = (bays: number): Set<number> => {
    if (bays >= 6) return new Set([1, bays - 2])
    if (bays >= 4) return new Set([Math.floor(bays / 2)])
    return new Set()
  }

  const addBox = (parent: THREE.Object3D, material: THREE.Material, width: number, height: number, depth: number,
    x: number, y: number, z: number, options?: { cast?: boolean; receive?: boolean; rotationY?: number }) => {
    const mesh = new THREE.Mesh(boxGeometry, material)
    mesh.scale.set(width, height, depth)
    mesh.position.set(x, y, z)
    if (options?.rotationY) mesh.rotation.y = options.rotationY
    mesh.castShadow = options?.cast ?? false
    mesh.receiveShadow = options?.receive ?? true
    parent.add(mesh)
    return mesh
  }
  const addRounded = (parent: THREE.Object3D, material: THREE.Material, width: number, height: number, depth: number,
    x: number, y: number, z: number, options?: { cast?: boolean; receive?: boolean }) => {
    const mesh = new THREE.Mesh(boardGeometry, material)
    mesh.scale.set(width, height, depth)
    mesh.position.set(x, y, z)
    mesh.castShadow = options?.cast ?? false
    mesh.receiveShadow = options?.receive ?? true
    parent.add(mesh)
    return mesh
  }
  /** 把一栋楼里的静态盒子按材质合并，避免几百个小 draw call；合批后的几何体随楼栋一起释放。 */
  const flushBoxes = (root: THREE.Object3D) => {
    root.updateMatrixWorld(true)
    const inverse = new THREE.Matrix4().copy(root.matrixWorld).invert()
    const buckets = new Map<string, { material: THREE.Material; cast: boolean; receive: boolean; geometries: THREE.BufferGeometry[]; meshes: THREE.Mesh[] }>()
    root.traverse(object => {
      if (!(object instanceof THREE.Mesh) || object instanceof THREE.InstancedMesh) return
      if (object.geometry !== boxGeometry) return
      object.updateMatrixWorld(true)
      tempMatrix.multiplyMatrices(inverse, object.matrixWorld)
      const bucketKey = `${(object.material as THREE.Material).uuid}:${object.castShadow ? 1 : 0}:${object.receiveShadow ? 1 : 0}`
      let bucket = buckets.get(bucketKey)
      if (!bucket) {
        bucket = { material: object.material as THREE.Material, cast: object.castShadow, receive: object.receiveShadow, geometries: [], meshes: [] }
        buckets.set(bucketKey, bucket)
      }
      bucket.geometries.push(boxGeometry.clone().applyMatrix4(tempMatrix))
      bucket.meshes.push(object)
    })
    for (const bucket of buckets.values()) {
      const merged = mergeGeometries(bucket.geometries, false)
      for (const geometry of bucket.geometries) geometry.dispose()
      if (!merged) continue
      const mesh = new THREE.Mesh(merged, bucket.material)
      mesh.castShadow = bucket.cast
      mesh.receiveShadow = bucket.receive
      mesh.userData.ownedGeometry = true
      for (const original of bucket.meshes) original.removeFromParent()
      root.add(mesh)
    }
  }

  const buildWindows = (building: THREE.Group, volume: BuildingVolume, model: BuildingModel, includeGround = false) => {
    const style = WINDOW_STYLE[model.facade]
    const frameGeometry = windowFrames.get(style)
    if (!frameGeometry) return
    const step = volume.height / volume.floors
    const startFloor = includeGround ? 0 : 1
    const rows = Math.max(0, volume.floors - startFloor)
    if (!rows) return
    const placements: { x: number; y: number; z: number; width: number; height: number; rotationY: number }[] = []
    for (const side of SIDES) {
      const ratio = model.glazing[side.name]
      if (ratio === null || ratio <= 0) continue
      const span = side.axis === 'z' ? volume.width : volume.depth
      const reach = side.axis === 'z' ? volume.depth : volume.width
      const bays = side.axis === 'z' ? model.bays : Math.max(2, Math.round(model.bays * .65))
      const bay = span / bays
      if (model.facade === 'frame') {
        // 框架体系用连续带形窗：每层一条横向玻璃带，外露柱/梁负责分格。
        const width = Math.max(.02, span * .88)
        const height = Math.max(.02, step * Math.min(.58, .34 + ratio * .45))
        for (let row = 0; row < rows; row++) {
          const floor = startFloor + row
          placements.push({
            x: side.axis === 'z' ? 0 : side.sign * (reach / 2 + .004),
            y: (floor + .5) * step,
            z: side.axis === 'z' ? side.sign * (reach / 2 + .004) : 0,
            width, height, rotationY: side.rotationY,
          })
        }
        continue
      }
      // MiC 是标准化墙板体系：窗户更小、墙板更大，避免读成一栋玻璃塔。
      const opening = Math.min(model.facade === 'modular' ? .72 : .84, Math.max(.3, Math.sqrt(ratio)))
      const width = Math.max(.02, bay * opening)
      const heightFactor = model.facade === 'modular'
        ? Math.min(.44, .34 + ratio * .18)
        : Math.min(.62, .44 + ratio * .2)
      const height = Math.max(.02, step * heightFactor)
      const solidBays = model.facade === 'hybrid' ? hybridSolidBays(bays) : undefined
      for (let row = 0; row < rows; row++) {
        const floor = startFloor + row
        for (let index = 0; index < bays; index++) {
          if (solidBays?.has(index)) continue
          const along = (index + .5) * bay - span / 2
          placements.push({
            x: side.axis === 'z' ? along : side.sign * (reach / 2 + .004),
            y: (floor + .5) * step,
            z: side.axis === 'z' ? side.sign * (reach / 2 + .004) : along,
            width, height, rotationY: side.rotationY,
          })
        }
      }
    }
    if (!placements.length) return
    const frames = new THREE.InstancedMesh(frameGeometry, model.facade === 'modular' ? stoneEdgeMaterial : metalDarkMaterial, placements.length)
    const panes = new THREE.InstancedMesh(glassGeometry, glassByFacade[model.facade], placements.length)
    for (let index = 0; index < placements.length; index++) {
      const placement = placements[index]
      tempQuaternion.setFromAxisAngle(Y_AXIS, placement.rotationY)
      tempPosition.set(placement.x, placement.y, placement.z)
      tempScale.set(placement.width, placement.height, 1)
      tempMatrix.compose(tempPosition, tempQuaternion, tempScale)
      frames.setMatrixAt(index, tempMatrix)
      panes.setMatrixAt(index, tempMatrix)
      // 每块玻璃有一点点色温差异，近看不像一张重复贴图。
      const variance = .9 + Math.abs(Math.sin(index * 4.37 + placements[index].y * 7.1)) * .16
      panes.setColorAt(index, new THREE.Color(variance * .96, variance, variance * .99))
    }
    frames.instanceMatrix.needsUpdate = true
    panes.instanceMatrix.needsUpdate = true
    if (panes.instanceColor) panes.instanceColor.needsUpdate = true
    frames.computeBoundingSphere(); panes.computeBoundingSphere()
    frames.castShadow = true; frames.receiveShadow = true
    panes.receiveShadow = true
    building.add(frames); building.add(panes)
  }

  // 框剪体系：隔几跨保留一道通高实墙肢，与整面开窗的框架方案区分。
  const buildHybridPiers = (building: THREE.Group, volume: BuildingVolume, model: BuildingModel) => {
    if (model.facade !== 'hybrid') return
    const placements: { x: number; y: number; z: number; sx: number; sz: number }[] = []
    for (const side of SIDES) {
      const span = side.axis === 'z' ? volume.width : volume.depth
      const reach = side.axis === 'z' ? volume.depth : volume.width
      const bays = side.axis === 'z' ? model.bays : Math.max(2, Math.round(model.bays * .65))
      const bay = span / bays
      for (const index of hybridSolidBays(bays)) {
        const along = (index + .5) * bay - span / 2
        const width = bay * .82
        placements.push({
          x: side.axis === 'z' ? along : side.sign * (reach / 2 + .018),
          y: volume.height / 2,
          z: side.axis === 'z' ? side.sign * (reach / 2 + .018) : along,
          sx: side.axis === 'z' ? width : .04,
          sz: side.axis === 'z' ? .04 : width,
        })
      }
    }
    if (!placements.length) return
    const piers = new THREE.InstancedMesh(boxGeometry, stoneMaterial, placements.length)
    for (let index = 0; index < placements.length; index++) {
      const placement = placements[index]
      tempMatrix.makeScale(placement.sx, volume.height, placement.sz)
      tempMatrix.setPosition(placement.x, placement.y, placement.z)
      piers.setMatrixAt(index, tempMatrix)
    }
    piers.instanceMatrix.needsUpdate = true
    piers.computeBoundingSphere()
    piers.castShadow = true; piers.receiveShadow = true
    building.add(piers)
  }

  const buildRibs = (building: THREE.Group, volume: BuildingVolume, model: BuildingModel) => {
    const material = model.facade === 'wall' ? stoneEdgeMaterial
      : model.facade === 'hybrid' ? stoneEdgeMaterial
        : model.facade === 'frame' ? metalMaterial
          : stoneEdgeMaterial
    const thickness = model.facade === 'wall' ? .045 : model.facade === 'frame' ? .034
      : model.facade === 'modular' ? .042 : .03
    const depth = model.facade === 'modular' ? .026 : .03
    const placements: { x: number; y: number; z: number; sx: number; sz: number }[] = []
    for (const side of SIDES) {
      const span = side.axis === 'z' ? volume.width : volume.depth
      const reach = side.axis === 'z' ? volume.depth : volume.width
      const bays = side.axis === 'z' ? model.bays : Math.max(2, Math.round(model.bays * .65))
      const bay = span / bays
      for (let index = 0; index <= bays; index++) {
        const along = index * bay - span / 2
        placements.push({
          x: side.axis === 'z' ? along : side.sign * (reach / 2 + depth / 2 + .001),
          y: volume.height / 2,
          z: side.axis === 'z' ? side.sign * (reach / 2 + depth / 2 + .001) : along,
          sx: side.axis === 'z' ? thickness : depth,
          sz: side.axis === 'z' ? depth : thickness,
        })
      }
    }
    const ribs = new THREE.InstancedMesh(boxGeometry, material, placements.length)
    for (let index = 0; index < placements.length; index++) {
      const placement = placements[index]
      tempMatrix.makeScale(placement.sx, volume.height, placement.sz)
      tempMatrix.setPosition(placement.x, placement.y, placement.z)
      ribs.setMatrixAt(index, tempMatrix)
    }
    ribs.instanceMatrix.needsUpdate = true
    ribs.computeBoundingSphere()
    ribs.castShadow = true; ribs.receiveShadow = true
    building.add(ribs)
    if (model.facade === 'hybrid' || model.facade === 'frame') {
      // 框架/框剪体系在正面加竖向遮阳鳍，让结构体系在体量上真的看得出来。
      const fins = new THREE.InstancedMesh(boxGeometry, model.facade === 'frame' ? metalMaterial : stoneEdgeMaterial, model.bays + 1)
      const bay = volume.width / model.bays
      for (let index = 0; index <= model.bays; index++) {
        tempMatrix.makeScale(.018, volume.height, .075)
        tempMatrix.setPosition(index * bay - volume.width / 2, volume.height / 2, volume.depth / 2 + .038)
        fins.setMatrixAt(index, tempMatrix)
      }
      fins.instanceMatrix.needsUpdate = true
      fins.computeBoundingSphere()
      fins.castShadow = true; fins.receiveShadow = true
      building.add(fins)
    }
    if (model.facade === 'wall' || model.facade === 'hybrid') {
      for (const x of [-volume.width / 2 + .018, volume.width / 2 - .018]) for (const z of [-volume.depth / 2 + .018, volume.depth / 2 - .018])
        addBox(building, bodyMaterials[model.facade], .036, volume.height, .036, x, volume.height / 2, z, { cast: true })
    }
    if (model.facade === 'frame') {
      // 框架体系在外角加通高金属角柱，与带形窗一起表达外露骨架。
      for (const x of [-volume.width / 2, volume.width / 2]) for (const z of [-volume.depth / 2, volume.depth / 2])
        addBox(building, metalMaterial, .055, volume.height, .055, x, volume.height / 2, z, { cast: true })
    }
  }

  const buildFloorBands = (building: THREE.Group, volume: BuildingVolume, model: BuildingModel) => {
    const step = volume.height / volume.floors
    const count = Math.max(0, volume.floors - 1)
    if (!count) return
    const material = model.facade === 'frame' ? metalMaterial : bandMaterial
    const thickness = model.facade === 'frame' ? .03 : model.facade === 'modular' ? .04 : .022
    const bands = new THREE.InstancedMesh(boxGeometry, material, count)
    for (let index = 0; index < count; index++) {
      const inset = model.facade === 'frame' ? .05 : model.facade === 'modular' ? .06 : .038
      tempMatrix.makeScale(volume.width + inset, thickness, volume.depth + inset)
      tempMatrix.setPosition(0, (index + 1) * step, 0)
      bands.setMatrixAt(index, tempMatrix)
    }
    bands.instanceMatrix.needsUpdate = true
    bands.computeBoundingSphere()
    bands.castShadow = true; bands.receiveShadow = true
    building.add(bands)
  }

  const buildLobby = (building: THREE.Group, volume: BuildingVolume, model: BuildingModel, rich: boolean) => {
    const step = volume.height / volume.floors
    const lobbyHeight = Math.min(step * 1.1, Math.max(.06, volume.height * .16))
    const glassPlacements: { x: number; y: number; z: number; width: number; rotationY: number }[] = []
    const mullionPlacements: { x: number; z: number; sx: number; sz: number }[] = []
    for (const side of SIDES) {
      const span = side.axis === 'z' ? volume.width : volume.depth
      const reach = side.axis === 'z' ? volume.depth : volume.width
      const bays = side.axis === 'z' ? model.bays : Math.max(2, Math.round(model.bays * .65))
      glassPlacements.push({
        x: side.axis === 'z' ? 0 : side.sign * (reach / 2 + .004),
        y: lobbyHeight * .47,
        z: side.axis === 'z' ? side.sign * (reach / 2 + .004) : 0,
        width: span * .8, rotationY: side.rotationY,
      })
      const bay = span / bays
      for (let index = 0; index <= bays; index++) {
        const along = index * bay - span / 2
        mullionPlacements.push({
          x: side.axis === 'z' ? along : side.sign * (reach / 2 + .011),
          z: side.axis === 'z' ? side.sign * (reach / 2 + .011) : along,
          sx: side.axis === 'z' ? .008 : .018,
          sz: side.axis === 'z' ? .018 : .008,
        })
      }
    }
    const lobbyGlass = new THREE.InstancedMesh(glassGeometry, glassDeepMaterial, glassPlacements.length)
    for (let index = 0; index < glassPlacements.length; index++) {
      const placement = glassPlacements[index]
      tempQuaternion.setFromAxisAngle(Y_AXIS, placement.rotationY)
      tempPosition.set(placement.x, placement.y, placement.z)
      tempScale.set(placement.width, lobbyHeight * .7, 1)
      tempMatrix.compose(tempPosition, tempQuaternion, tempScale)
      lobbyGlass.setMatrixAt(index, tempMatrix)
    }
    lobbyGlass.instanceMatrix.needsUpdate = true
    lobbyGlass.computeBoundingSphere()
    lobbyGlass.receiveShadow = true
    building.add(lobbyGlass)
    const mullions = new THREE.InstancedMesh(boxGeometry, metalDarkMaterial, mullionPlacements.length)
    for (let index = 0; index < mullionPlacements.length; index++) {
      const placement = mullionPlacements[index]
      tempMatrix.makeScale(placement.sx, lobbyHeight * .7, placement.sz)
      tempMatrix.setPosition(placement.x, lobbyHeight * .47, placement.z)
      mullions.setMatrixAt(index, tempMatrix)
    }
    mullions.instanceMatrix.needsUpdate = true
    mullions.computeBoundingSphere()
    building.add(mullions)
    addBox(building, stoneEdgeMaterial, volume.width + .03, .012, volume.depth + .03, 0, lobbyHeight, 0, { cast: true })
    // 入口雨棚和台阶只在前侧做，让正面有真实使用尺度；其余面保持干净的玻璃基座。
    const portalWidth = volume.width * .28, portalHeight = lobbyHeight * .88
    addBox(building, glassDeepMaterial, portalWidth, portalHeight, .014, 0, portalHeight / 2 + .008, volume.depth / 2 + .012)
    addBox(building, metalDarkMaterial, portalWidth + .026, .012, .026, 0, portalHeight + .008, volume.depth / 2 + .012)
    if (rich) {
      const canopyZ = volume.depth / 2 + .11
      addBox(building, paperMaterial, volume.width * .42, .016, .2, 0, lobbyHeight * 1.03, canopyZ, { cast: true })
      addBox(building, metalDarkMaterial, volume.width * .42, .024, .016, 0, lobbyHeight * 1.03 - .019, canopyZ + .088, { cast: true })
      for (const x of [-volume.width * .16, volume.width * .16])
        addBox(building, metalDarkMaterial, .012, lobbyHeight * 1.02, .012, x, lobbyHeight * .51, canopyZ + .072, { cast: true })
      addBox(building, stoneEdgeMaterial, volume.width * .32, .014, .09, 0, .027, volume.depth / 2 + .075, { cast: true })
      addBox(building, stoneEdgeMaterial, volume.width * .38, .014, .08, 0, .041, volume.depth / 2 + .13, { cast: true })
      for (const x of [-volume.width * .26, volume.width * .26]) {
        addBox(building, stoneMaterial, volume.width * .09, .032, volume.depth * .08, x, .03, volume.depth / 2 + .06, { cast: true })
        addBox(building, plantMaterial, volume.width * .075, .026, volume.depth * .06, x, .055, volume.depth / 2 + .06, { cast: true })
      }
    }
  }

  const buildRoof = (building: THREE.Group, volume: BuildingVolume, model: BuildingModel, index: number, rich: boolean) => {
    const top = volume.height
    const width = volume.width, depth = volume.depth
    addBox(building, bodyMaterials[model.facade], width - .026, .006, depth - .026, 0, top + .004, 0)
    for (const z of [-depth / 2 + .007, depth / 2 - .007])
      addBox(building, bodyMaterials[model.facade], width + .028, .046, .014, 0, top + .023, z, { cast: true })
    for (const x of [-width / 2 + .007, width / 2 - .007])
      addBox(building, bodyMaterials[model.facade], .014, .046, depth + .028, x, top + .023, 0, { cast: true })
    for (const z of [-depth / 2 + .007, depth / 2 - .007])
      addBox(building, paperMaterial, width + .05, .008, .026, 0, top + .05, z, { cast: true })
    for (const x of [-width / 2 + .007, width / 2 - .007])
      addBox(building, paperMaterial, .026, .008, depth + .05, x, top + .05, 0, { cast: true })
    addBox(building, roofMaterial, width - .05, .004, depth - .05, 0, top + .009, 0)
    addBox(building, roofDeckMaterial, width - .1, .006, depth - .1, 0, top + .012, 0)
    const mechWidth = width * .26, mechDepth = depth * .28
    const mechX = width * .12, mechZ = -depth * .12
    addBox(building, stoneMaterial, mechWidth, .086, mechDepth, mechX, top + .047, mechZ, { cast: true })
    addBox(building, paperMaterial, mechWidth + .026, .008, mechDepth + .026, mechX, top + .094, mechZ, { cast: true })
    for (let line = 0; line < 3; line++)
      addBox(building, louverMaterial, mechWidth * .82, .005, .006, mechX, top + .026 + line * .015, mechZ + mechDepth / 2 + .004)
    addBox(building, stoneMaterial, width * .09, .046, depth * .11, -width * .18, top + .027, -depth * .16, { cast: true })
    const units = rich ? 3 : 1
    for (let unit = 0; unit < units; unit++) {
      const x = width * (.24 + unit * .09), z = depth * (.2 - (unit % 2) * .12)
      addBox(building, metalMaterial, width * .07, .026, depth * .07, x, top + .02, z, { cast: true })
      addBox(building, louverMaterial, width * .05, .004, depth * .05, x, top + .034, z)
    }
    // 屋顶栏杆和一道细阴影线，让天际线不是一块白盒子。
    for (const z of [-depth / 2 + .02, depth / 2 - .02])
      addBox(building, metalMaterial, width - .04, .004, .004, 0, top + .064, z)
    for (const x of [-width / 2 + .02, width / 2 - .02])
      addBox(building, metalMaterial, .004, .004, depth - .04, x, top + .064, 0)
    if (index % 2 === 1 && rich) {
      // 奇数栋加一段屋面格栅，用最少的构件拉开栋与栋的轮廓差异。
      const screenWidth = width * .46
      addBox(building, metalDarkMaterial, screenWidth, .012, .012, 0, top + .058, -depth / 2 + .04, { cast: true })
      for (let fin = -2; fin <= 2; fin++)
        addBox(building, metalDarkMaterial, .008, .05, .03, fin * screenWidth / 5, top + .034, -depth / 2 + .04, { cast: true })
    }
  }

  const buildCantilever = (building: THREE.Group, volume: BuildingVolume, model: BuildingModel) => {
    if (!model.cantilever) return
    const step = volume.height / volume.floors
    for (const fraction of [.32, .68]) {
      const y = Math.round(volume.floors * fraction) * step
      if (y <= 0 || y >= volume.height) continue
      addBox(building, stoneEdgeMaterial, volume.width + .14, .026, volume.depth + .18, 0, y, 0, { cast: true })
      addBox(building, paperMaterial, volume.width + .16, .008, volume.depth + .2, 0, y + .017, 0, { cast: true })
      addBox(building, metalDarkMaterial, volume.width + .16, .006, volume.depth + .2, 0, y - .016, 0)
    }
  }

  const buildVolume = (volume: BuildingVolume, model: BuildingModel, index: number, rich: boolean) => {
    const building = new THREE.Group()
    building.position.set(volume.x, 0, volume.z)
    const step = volume.height / volume.floors
    // 顶部两到三层收进：楼层数不变，但天际线不再是一排相同的盒子。
    const crownFloors = volume.floors >= 10 ? (index % 2 === 0 ? 3 : 2) : 0
    const crownScale = .73 + (index % 2) * .06
    const mainFloors = volume.floors - crownFloors
    const mainHeight = mainFloors * step
    const mainVolume: BuildingVolume = { ...volume, height: mainHeight, floors: mainFloors }
    const body = new THREE.Mesh(roundedGeometry, bodyMaterials[model.facade])
    body.scale.set(mainVolume.width, mainVolume.height, mainVolume.depth)
    body.position.y = mainVolume.height / 2
    body.castShadow = true; body.receiveShadow = true
    building.add(body)
    addBox(building, stoneMaterial, volume.width + .04, .03, volume.depth + .04, 0, .015, 0, { cast: true })
    buildWindows(building, mainVolume, model)
    buildHybridPiers(building, mainVolume, model)
    buildRibs(building, mainVolume, model)
    buildFloorBands(building, mainVolume, model)
    buildLobby(building, mainVolume, model, rich)
    buildCantilever(building, mainVolume, model)
    if (model.facade === 'hybrid' && mainFloors >= 8) {
      // 框剪方案加一道中部结构腰带，暗示转换/加强层；框架方案则保持通高外露柱。
      const beltY = Math.round(mainFloors * .5) * step
      addBox(building, metalMaterial, volume.width + .07, .032, volume.depth + .07, 0, beltY, 0, { cast: true })
      addBox(building, paperMaterial, volume.width + .08, .008, volume.depth + .08, 0, beltY + .019, 0, { cast: true })
    }
    // 剪力墙住宅在正面做一条节奏明确的生活阳台，避免整栋看起来只是窗格纸。
    if (model.facade === 'wall' && model.glazing['南'] !== null && model.glazing['南'] > 0 && mainFloors >= 5) {
      const balconyFloors: number[] = []
      for (let floor = 2; floor <= mainFloors - 2; floor += 2) balconyFloors.push(floor)
      const ledges = new THREE.InstancedMesh(boxGeometry, stoneEdgeMaterial, balconyFloors.length)
      const rails = new THREE.InstancedMesh(boxGeometry, glassDeepMaterial, balconyFloors.length)
      const caps = new THREE.InstancedMesh(boxGeometry, metalMaterial, balconyFloors.length)
      for (let balcony = 0; balcony < balconyFloors.length; balcony++) {
        const y = balconyFloors[balcony] * step
        tempMatrix.makeScale(volume.width * .94, .016, .07)
        tempMatrix.setPosition(0, y, volume.depth / 2 + .035)
        ledges.setMatrixAt(balcony, tempMatrix)
        tempMatrix.makeScale(volume.width * .94, .032, .006)
        tempMatrix.setPosition(0, y + .026, volume.depth / 2 + .066)
        rails.setMatrixAt(balcony, tempMatrix)
        tempMatrix.makeScale(volume.width * .94, .004, .01)
        tempMatrix.setPosition(0, y + .044, volume.depth / 2 + .066)
        caps.setMatrixAt(balcony, tempMatrix)
      }
      ledges.instanceMatrix.needsUpdate = true; rails.instanceMatrix.needsUpdate = true; caps.instanceMatrix.needsUpdate = true
      ledges.computeBoundingSphere(); rails.computeBoundingSphere(); caps.computeBoundingSphere()
      ledges.castShadow = true; rails.castShadow = true; caps.castShadow = true
      building.add(ledges); building.add(rails); building.add(caps)
    }
    if (!crownFloors) {
      buildRoof(building, volume, model, index, rich)
      flushBoxes(building)
      return building
    }
    const crownHeight = crownFloors * step
    const crownWidth = volume.width * crownScale, crownDepth = volume.depth * crownScale
    const crownVolume: BuildingVolume = { x: 0, z: 0, width: crownWidth, depth: crownDepth, height: crownHeight, floors: crownFloors }
    // 退台屋面：一圈露台、玻璃栏板和金属压顶，让收进的关系可读。
    addBox(building, terraceMaterial, volume.width - .02, .01, volume.depth - .02, 0, mainHeight + .005, 0)
    const railHeight = .034
    for (const z of [-volume.depth / 2 + .012, volume.depth / 2 - .012])
      addBox(building, glassDeepMaterial, volume.width - .03, railHeight, .006, 0, mainHeight + .027, z)
    for (const x of [-volume.width / 2 + .012, volume.width / 2 - .012])
      addBox(building, glassDeepMaterial, .006, railHeight, volume.depth - .03, x, mainHeight + .027, 0)
    for (const z of [-volume.depth / 2 + .012, volume.depth / 2 - .012])
      addBox(building, metalMaterial, volume.width - .03, .004, .01, 0, mainHeight + .046, z)
    for (const x of [-volume.width / 2 + .012, volume.width / 2 - .012])
      addBox(building, metalMaterial, .01, .004, volume.depth - .03, x, mainHeight + .046, 0)
    const crown = new THREE.Group()
    crown.position.y = mainHeight
    building.add(crown)
    const crownBody = new THREE.Mesh(roundedGeometry, bodyMaterials[model.facade])
    crownBody.scale.set(crownVolume.width, crownVolume.height, crownVolume.depth)
    crownBody.position.y = crownVolume.height / 2
    crownBody.castShadow = true; crownBody.receiveShadow = true
    crown.add(crownBody)
    buildWindows(crown, crownVolume, model, true)
    buildHybridPiers(crown, crownVolume, model)
    buildRibs(crown, crownVolume, model)
    buildFloorBands(crown, crownVolume, model)
    buildRoof(crown, crownVolume, model, index, rich)
    flushBoxes(building)
    return building
  }

  const buildSite = (model: BuildingModel, boardWidth: number, boardDepth: number, centerX: number, centerZ: number) => {
    const group = new THREE.Group()
    group.position.set(centerX, 0, centerZ)
    addRounded(group, boardMaterial, boardWidth, .18, boardDepth, 0, -.09, 0)
    addRounded(group, terraceMaterial, boardWidth - .14, .02, boardDepth - .14, 0, .01, 0)
    addBox(group, pathMaterial, boardWidth * .11, .006, boardDepth * .36, 0, .024, boardDepth * .28)
    const bedSpots: [number, number, number, number][] = [
      [-.31, .33, .18, .08], [.31, .33, .18, .08], [-.02, -.4, .30, .07],
    ]
    for (const [x, z, w, d] of bedSpots) {
      addBox(group, stoneEdgeMaterial, boardWidth * w, .026, boardDepth * d, boardWidth * x, .034, boardDepth * z, { cast: true })
      addBox(group, plantMaterial, boardWidth * w * .88, .024, boardDepth * d * .8, boardWidth * x, .055, boardDepth * z, { cast: true })
    }
    // 低模树作为尺度参照；位置固定，避免每次切换方案时场景跳动。
    const treeSpots: [number, number][] = [
      [-.82, .76], [-.52, .84], [.52, .84], [.82, .76],
      [-.87, .08], [.87, .02], [-.82, -.72], [.82, -.74], [-.34, -.86], [.34, -.86],
    ]
    const trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, treeSpots.length)
    const foliage = new THREE.InstancedMesh(foliageGeometry, treeMaterial, treeSpots.length)
    for (let index = 0; index < treeSpots.length; index++) {
      const [spotX, spotZ] = treeSpots[index]
      const scale = 1.45 + Math.abs(Math.sin(index * 2.17 + 1.3)) * .55
      const x = spotX * boardWidth * .5, z = spotZ * boardDepth * .5
      tempQuaternion.identity()
      tempPosition.set(x, .02, z); tempScale.set(scale, scale, scale)
      tempMatrix.compose(tempPosition, tempQuaternion, tempScale)
      trunks.setMatrixAt(index, tempMatrix)
      tempPosition.set(x, .02 + .13 * scale, z)
      tempMatrix.compose(tempPosition, tempQuaternion, tempScale)
      foliage.setMatrixAt(index, tempMatrix)
      foliage.setColorAt(index, new THREE.Color(index % 2 ? tokens.scene.plantAlt : tokens.scene.plant))
    }
    trunks.instanceMatrix.needsUpdate = true; foliage.instanceMatrix.needsUpdate = true
    if (foliage.instanceColor) foliage.instanceColor.needsUpdate = true
    trunks.computeBoundingSphere(); foliage.computeBoundingSphere()
    trunks.castShadow = true; foliage.castShadow = true
    group.add(trunks); group.add(foliage)
    const contacts = new THREE.InstancedMesh(contactGeometry, contactMaterial, model.volumes.length)
    for (let index = 0; index < model.volumes.length; index++) {
      const volume = model.volumes[index]
      tempMatrix.makeScale(Math.max(.7, volume.width * 1.75), 1, Math.max(.7, volume.depth * 1.75))
      tempMatrix.setPosition(volume.x - centerX, .023, volume.z - centerZ)
      contacts.setMatrixAt(index, tempMatrix)
    }
    contacts.instanceMatrix.needsUpdate = true
    contacts.computeBoundingSphere()
    contacts.renderOrder = 2
    group.add(contacts)
    const boardShadow = new THREE.Mesh(contactGeometry, boardShadowMaterial)
    boardShadow.scale.set(boardWidth * 1.32, 1, boardDepth * 1.32)
    boardShadow.position.y = -.38
    boardShadow.renderOrder = 1
    group.add(boardShadow)
    return group
  }

  const updateShadowCamera = (boardWidth: number, boardDepth: number) => {
    const extent = Math.max(boardWidth, boardDepth) * 1.15 + 1.4
    const shadowCamera = sun.shadow.camera
    shadowCamera.left = -extent; shadowCamera.right = extent
    shadowCamera.top = extent; shadowCamera.bottom = -extent
    shadowCamera.near = 1; shadowCamera.far = 42
    shadowCamera.updateProjectionMatrix()
    sun.position.set(focus.x - 7.4, focus.y + 6.6, focus.z + 5.4)
    sun.target.position.copy(focus)
    sun.target.updateMatrixWorld()
  }

  const applyCamera = () => {
    const verticalFov = camera.fov * DEG
    const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect)
    const distance = Math.max(fitRadius / Math.sin(verticalFov / 2), fitRadius / Math.sin(horizontalFov / 2)) * 1.14
    const azimuth = .66 + yaw, elevation = .49 + pitch
    camera.position.set(
      focus.x + Math.sin(azimuth) * Math.cos(elevation) * distance,
      focus.y + Math.sin(elevation) * distance,
      focus.z + Math.cos(azimuth) * Math.cos(elevation) * distance,
    )
    camera.lookAt(focus)
    camera.updateMatrixWorld()
  }

  const update = (model: BuildingModel) => {
    if (disposed || failed) return
    // 只重建体量与场地；相机、环境、灯光和共享几何体保持复用。
    for (const group of [volumes, site]) {
      world.remove(group)
      group.traverse(object => {
        if (object instanceof THREE.InstancedMesh) object.dispose()
        else if (object instanceof THREE.Mesh && object.userData.ownedGeometry) object.geometry.dispose()
      })
      group.clear()
    }
    volumes = new THREE.Group()
    site = new THREE.Group()
    world.add(volumes); world.add(site)
    const rich = model.volumes.length <= 6
    for (let index = 0; index < model.volumes.length; index++) {
      const volume = model.volumes[index]
      const building = buildVolume(volume, model, index, rich)
      volumes.add(building)
    }
    if (model.volumes.length) {
      const minX = Math.min(...model.volumes.map(volume => volume.x - volume.width / 2))
      const maxX = Math.max(...model.volumes.map(volume => volume.x + volume.width / 2))
      const minZ = Math.min(...model.volumes.map(volume => volume.z - volume.depth / 2))
      const maxZ = Math.max(...model.volumes.map(volume => volume.z + volume.depth / 2))
      const centerX = (minX + maxX) / 2, centerZ = (minZ + maxZ) / 2
      const boardWidth = Math.max(3, maxX - minX + 2)
      const boardDepth = Math.max(2.5, maxZ - minZ + 1.8)
      const siteGroup = buildSite(model, boardWidth, boardDepth, centerX, centerZ)
      site.add(siteGroup)
      const bounds = new THREE.Box3().setFromObject(volumes)
      const size = bounds.getSize(new THREE.Vector3())
      const center = bounds.getCenter(new THREE.Vector3())
      focus.set(center.x, bounds.min.y + size.y * .48, center.z)
      const sphere = bounds.getBoundingSphere(new THREE.Sphere())
      fitRadius = Math.max(1.05, sphere.radius * 1.04, Math.min(boardWidth, boardDepth) * .36)
      updateShadowCamera(boardWidth, boardDepth)
      host.dataset.facade = model.facade
      renderer.shadowMap.needsUpdate = true
      applyCamera()
      requestRender()
    }
  }
  const down = (event: PointerEvent) => {
    if (event.button !== 0) return
    targetYaw = yaw; targetPitch = pitch
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, yaw: targetYaw, pitch: targetPitch }
    canvas.setPointerCapture(event.pointerId)
    canvas.classList.add('is-dragging')
  }
  const move = (event: PointerEvent) => {
    if (event.pointerId !== pointer?.id) return
    targetYaw = pointer.yaw + (event.clientX - pointer.x) * .0045
    targetPitch = THREE.MathUtils.clamp(pointer.pitch + (event.clientY - pointer.y) * .0015, -.16, .2)
    requestRender()
  }
  const up = (event: PointerEvent) => {
    if (event.pointerId !== pointer?.id) return
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
    pointer = undefined; canvas.classList.remove('is-dragging')
    lastTick = 0; lastDraw = 0; requestRender()
  }
  const reset = () => {
    pauseAuto()
    targetYaw = yaw + Math.atan2(Math.sin(-yaw), Math.cos(-yaw))
    targetPitch = 0
    requestRender()
  }
  const pauseAuto = () => {
    pauseUntil = performance.now() + 2400
    clearTimeout(resumeTimer)
    resumeTimer = setTimeout(() => { resumeTimer = undefined; lastTick = 0; lastDraw = 0; requestRender() }, 2400)
  }
  const key = (event: KeyboardEvent) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home'].includes(event.key)) return
    event.preventDefault()
    pauseAuto()
    if (event.key === 'Home') reset()
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') targetYaw += event.key === 'ArrowLeft' ? -.12 : .12
    else targetPitch = THREE.MathUtils.clamp(targetPitch + (event.key === 'ArrowUp' ? -.04 : .04), -.13, .17)
    requestRender()
  }
  const fail = () => {
    if (disposed || failed) return
    failed = true
    cancelAnimationFrame(frame); frame = 0
    onUnavailable()
  }
  const render = (now: number) => {
    frame = 0
    if (disposed || failed || !visible || document.hidden) { lastTick = 0; lastDraw = 0; return }
    const spinning = !reduce.matches && !pointer && now >= pauseUntil
    // 慢转按经过时间计算，并将连续 GPU 绘制限制在约 30fps。
    if (spinning && lastDraw && now - lastDraw < 1000 / 30 - .5) { requestRender(); return }
    const elapsed = lastTick ? Math.min((now - lastTick) / 1000, .08) : 0
    lastTick = now; lastDraw = now
    if (spinning) {
      targetYaw += elapsed * TAU / 150
      if (Math.abs(targetYaw) > TAU) { const offset = Math.trunc(targetYaw / TAU) * TAU; targetYaw -= offset; yaw -= offset }
    }
    const ease = reduce.matches ? 1 : .18
    yaw += (targetYaw - yaw) * ease
    pitch += (targetPitch - pitch) * ease
    applyCamera()
    try { renderer.render(scene, camera); if (!ready) { ready = true; onReady() } } catch (error) {
      if (import.meta.env.DEV) console.error('建筑体量展台渲染失败', error)
      fail(); return
    }
    if (spinning || Math.abs(targetYaw - yaw) > .001 || Math.abs(targetPitch - pitch) > .001) requestRender()
  }
  const requestRender = () => { if (!frame && !disposed && !failed && visible && !document.hidden) frame = requestAnimationFrame(render) }
  const resize = () => {
    const width = host.clientWidth, height = host.clientHeight
    if (!width || !height || disposed) return
    renderer.setSize(width, height)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    applyCamera()
    requestRender()
  }
  const contextLost = (event: Event) => { event.preventDefault(); fail() }
  const visibility = () => {
    lastTick = 0; lastDraw = 0
    if (document.hidden) { cancelAnimationFrame(frame); frame = 0 } else requestRender()
  }
  const motionChange = () => { lastTick = 0; lastDraw = 0; requestRender() }
  cleanups.push(() => {
    canvas.removeEventListener('pointerdown', down); canvas.removeEventListener('pointermove', move)
    canvas.removeEventListener('pointerup', up); canvas.removeEventListener('pointercancel', up)
    canvas.removeEventListener('lostpointercapture', up); canvas.removeEventListener('keydown', key)
    canvas.removeEventListener('webglcontextlost', contextLost)
    document.removeEventListener('visibilitychange', visibility); reduce.removeEventListener('change', motionChange)
  })
  canvas.addEventListener('pointerdown', down)
  canvas.addEventListener('pointermove', move)
  canvas.addEventListener('pointerup', up)
  canvas.addEventListener('pointercancel', up)
  canvas.addEventListener('lostpointercapture', up)
  canvas.addEventListener('keydown', key)
  canvas.addEventListener('webglcontextlost', contextLost)
  document.addEventListener('visibilitychange', visibility)
  reduce.addEventListener('change', motionChange)
  const observer = new ResizeObserver(resize)
  cleanups.push(() => observer.disconnect())
  observer.observe(host)
  const intersection = new IntersectionObserver(entries => {
    visible = entries[0]?.isIntersecting ?? true
    lastTick = 0; lastDraw = 0
    if (!visible) { cancelAnimationFrame(frame); frame = 0 } else requestRender()
  })
  cleanups.push(() => intersection.disconnect())
  intersection.observe(host)
  resize()
  return { update, reset, dispose }
  } catch (error) { dispose(); throw error }
}

const BuildingScene = forwardRef<BuildingSceneHandle, { model: BuildingModel; onUnavailable: () => void; onReady: () => void }>(function BuildingScene({ model, onUnavailable, onReady }, ref) {
  const host = useRef<HTMLDivElement>(null)
  const controller = useRef<Controller>()
  const latest = useRef(model)
  latest.current = model
  useImperativeHandle(ref, () => ({ reset: () => controller.current?.reset() }), [])
  useEffect(() => {
    if (!host.current) return
    try { controller.current = createScene(host.current, onUnavailable, onReady); controller.current.update(latest.current) }
    catch (error) {
      if (import.meta.env.DEV) console.error('建筑体量展台初始化失败', error)
      controller.current?.dispose(); controller.current = undefined; onUnavailable()
    }
    return () => { controller.current?.dispose(); controller.current = undefined }
  }, [onUnavailable, onReady])
  useEffect(() => { controller.current?.update(model) }, [model])
  return <div className="building-canvas" ref={host} data-renderer="webgl" />
})
export default BuildingScene
