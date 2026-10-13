import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import type { BuildingModel, FacadeSide } from './building-model'
import { tokens } from '../theme'

interface Controller { update: (model: BuildingModel) => void; reset: () => void; dispose: () => void }

/** 可见时缓慢环绕；拖动、减少动态效果与不可见状态下暂停自动旋转。 */
function createScene(host: HTMLDivElement, onUnavailable: () => void, onReady: () => void): Controller {
  let disposed = false, frame = 0
  let allocatedRenderer: THREE.WebGLRenderer | undefined
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
    try { allocatedRenderer?.dispose() } catch { /* 仍要释放上下文 */ }
    try { allocatedRenderer?.forceContextLoss() } catch { /* 上下文可能已经丢失 */ }
    allocatedRenderer = undefined
  }
  try {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' })
  allocatedRenderer = renderer
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, innerWidth < 768 ? 1.25 : 1.75))
  renderer.setClearColor(0x000000, 0)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = .98
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
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
    scene.traverse(object => { if (object instanceof THREE.InstancedMesh) object.dispose() })
    scene.clear()
  })
  // 本地程序化摄影棚反射，不下载 HDR；各项在下一步分配前注册释放。
  const studio = new RoomEnvironment()
  cleanups.push(() => studio.dispose())
  const environmentGenerator = new THREE.PMREMGenerator(renderer)
  cleanups.push(() => environmentGenerator.dispose())
  const environment = environmentGenerator.fromScene(studio, .04)
  cleanups.push(() => { scene.environment = null; environment.dispose() })
  scene.environment = environment.texture
  scene.environmentIntensity = .45
  const camera = new THREE.OrthographicCamera(-5, 5, 4.5, -4.5, .1, 70)
  camera.up.set(0, 1, 0)
  const focus = new THREE.Vector3(0, 1.15, 0)
  camera.zoom = 1.15
  const world = new THREE.Group()
  scene.add(world)
  const bounds = new THREE.Box3()
  const corner = new THREE.Vector3()
  const ambient = new THREE.HemisphereLight(tokens.surface, tokens.scene.edge, 1.65)
  scene.add(ambient)
  const main = new THREE.DirectionalLight(tokens.surface, 2.5)
  main.position.set(-5, 9, 7)
  main.castShadow = true
  cleanups.push(() => main.shadow.dispose())
  main.shadow.mapSize.set(1024, 1024)
  main.shadow.camera.left = -6; main.shadow.camera.right = 6
  main.shadow.camera.top = 6; main.shadow.camera.bottom = -6
  main.shadow.bias = -.001
  scene.add(main)
  const mint = new THREE.PointLight(tokens.glowMint, 1.8, 20, 1.4)
  mint.position.set(-4, 4, 2); scene.add(mint)
  const lilac = new THREE.PointLight(tokens.glowLilac, 2.4, 20, 1.4)
  lilac.position.set(5, 5, -3); scene.add(lilac)
  const boxGeometry = keep(new THREE.BoxGeometry(1, 1, 1))
  const bodyGeometry = keep(new RoundedBoxGeometry(1, 1, 1, 2, .008))
  const bodyMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.building, roughness: .62 }))
  const facadeMaterial = keep(new THREE.MeshPhysicalMaterial({ color: tokens.scene.facade, roughness: .19, metalness: .28, clearcoat: .85 }))
  const roofMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.roof, roughness: .42 }))
  const floorMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.frame, roughness: .5 }))
  const jointMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.module, roughness: .58 }))
  const insetMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.inset, roughness: .45 }))
  const rooftopMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.rooftop, roughness: .72 }))
  const plateGeometry = keep(new RoundedBoxGeometry(6.45, .12, 5.3, 3, .04))
  const plateMaterial = keep(new THREE.MeshPhysicalMaterial({ color: tokens.scene.plate, roughness: .19, metalness: .10, transparent: true, opacity: .38, clearcoat: 1, depthWrite: false }))
  const plate = new THREE.Mesh(plateGeometry, plateMaterial)
  plate.position.y = -.08; plate.receiveShadow = true; world.add(plate)
  const rimGeometry = keep(new RoundedBoxGeometry(6.54, .045, 5.38, 3, .025))
  const rimMaterial = keep(new THREE.MeshPhysicalMaterial({ color: tokens.scene.roof, transparent: true, opacity: .72, roughness: .12, metalness: .2 }))
  const rim = new THREE.Mesh(rimGeometry, rimMaterial)
  rim.position.y = -.06; world.add(rim)
  const shadowGeometry = keep(new THREE.PlaneGeometry(14, 14))
  const shadowMaterial = keep(new THREE.ShadowMaterial({ opacity: .09 }))
  const shadow = new THREE.Mesh(shadowGeometry, shadowMaterial)
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = -.68; shadow.receiveShadow = true; scene.add(shadow)

  let volumes = new THREE.Group()
  world.add(volumes)
  let failed = false, visible = true, ready = false
  let yaw = 0, targetYaw = yaw, pitch = 0, targetPitch = 0
  let pointer: { id: number; x: number; y: number; yaw: number; pitch: number } | undefined
  let lastTick = 0, lastDraw = 0, pauseUntil = 0
  let resumeTimer: ReturnType<typeof setTimeout> | undefined
  cleanups.push(() => clearTimeout(resumeTimer))
  const turn = Math.PI * 2
  const pauseAuto = () => {
    pauseUntil = performance.now() + 2200
    clearTimeout(resumeTimer)
    resumeTimer = setTimeout(() => { resumeTimer = undefined; lastTick = 0; lastDraw = 0; requestRender() }, 2200)
  }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)')
  const matrix = new THREE.Matrix4()
  const fail = () => { if (!failed && !disposed) { failed = true; cancelAnimationFrame(frame); frame = 0; onUnavailable() } }
  const render = (now: number) => {
    frame = 0
    if (disposed || failed || !visible || document.hidden) { lastTick = 0; lastDraw = 0; return }
    const spinning = !reduce.matches && !pointer && now >= pauseUntil
    // 慢转按经过时间计算，并将连续 GPU 绘制限制在约 30fps。
    if (spinning && lastDraw && now - lastDraw < 1000 / 30 - .5) { requestRender(); return }
    const elapsed = lastTick ? Math.min((now - lastTick) / 1000, .08) : 0
    lastTick = now; lastDraw = now
    if (spinning) {
      targetYaw += elapsed * turn / 120
      if (Math.abs(targetYaw) > turn) { const offset = Math.trunc(targetYaw / turn) * turn; targetYaw -= offset; yaw -= offset }
    }
    const ease = reduce.matches ? 1 : .18
    yaw += (targetYaw - yaw) * ease
    pitch += (targetPitch - pitch) * ease
    // 始终以 Y 为竖直轴绕建筑观察，绝不倾斜或压扁楼体。
    const azimuth = .58 + yaw, elevation = .43 + pitch, radius = 14
    camera.position.set(Math.sin(azimuth) * Math.cos(elevation) * radius,
      focus.y + Math.sin(elevation) * radius, Math.cos(azimuth) * Math.cos(elevation) * radius)
    camera.lookAt(focus)
    camera.updateMatrixWorld()
    if (!bounds.isEmpty()) {
      let halfWidth = 0, halfHeight = 0
      for (const x of [bounds.min.x, bounds.max.x]) for (const y of [bounds.min.y, bounds.max.y]) for (const z of [bounds.min.z, bounds.max.z]) {
        corner.set(x, y, z).applyMatrix4(camera.matrixWorldInverse)
        halfWidth = Math.max(halfWidth, Math.abs(corner.x)); halfHeight = Math.max(halfHeight, Math.abs(corner.y))
      }
      camera.zoom = Math.min(1.5, camera.right * .86 / Math.max(halfWidth, .1), camera.top * .82 / Math.max(halfHeight, .1))
      camera.updateProjectionMatrix()
    }
    try { renderer.render(scene, camera); if (!ready) { ready = true; onReady() } } catch { fail(); return }
    if (spinning || Math.abs(targetYaw - yaw) > .001 || Math.abs(targetPitch - pitch) > .001) requestRender()
  }
  const requestRender = () => { if (!frame && !disposed && !failed && visible && !document.hidden) frame = requestAnimationFrame(render) }
  const resize = () => {
    const width = host.clientWidth, height = host.clientHeight
    if (!width || !height || disposed) return
    renderer.setSize(width, height)
    camera.left = -4.5 * width / height; camera.right = 4.5 * width / height
    camera.updateProjectionMatrix()
    requestRender()
  }
  const update = (model: BuildingModel) => {
    if (disposed || failed) return
    // InstancedMesh 自带的实例缓冲也需要 dispose；共享 geometry/material 只在卸载释放。
    volumes.traverse(object => { if (object instanceof THREE.InstancedMesh) object.dispose() })
    world.remove(volumes); volumes = new THREE.Group(); world.add(volumes)
    for (const volume of model.volumes) {
      const building = new THREE.Group()
      building.position.set(volume.x, 0, volume.z)
      const body = new THREE.Mesh(bodyGeometry, bodyMaterial)
      body.scale.set(volume.width, volume.height, volume.depth)
      body.position.y = volume.height / 2; body.castShadow = true; body.receiveShadow = true; building.add(body)
      const step = volume.height / volume.floors
      // 四面独立窗洞，避免整块半透明立面和实体重叠造成的排序/闪烁。
      const sides: { name: FacadeSide; axis: 'x' | 'z'; sign: number; span: number; reach: number }[] = [
        { name: '南', axis: 'z', sign: 1, span: volume.width, reach: volume.depth },
        { name: '北', axis: 'z', sign: -1, span: volume.width, reach: volume.depth },
        { name: '东', axis: 'x', sign: 1, span: volume.depth, reach: volume.width },
        { name: '西', axis: 'x', sign: -1, span: volume.depth, reach: volume.width },
      ]
      for (const side of sides) {
        const ratio = model.glazing[side.name]
        const bays = side.axis === 'z' ? model.bays : Math.max(2, Math.round(model.bays * .65))
        const bay = side.span / bays
        if (ratio !== null && ratio > 0) {
          const windows = new THREE.InstancedMesh(boxGeometry, facadeMaterial, bays * volume.floors)
          const opening = Math.min(.92, Math.sqrt(ratio))
          for (let floor = 0; floor < volume.floors; floor++) for (let index = 0; index < bays; index++) {
            const along = (index + .5) * bay - side.span / 2
            matrix.makeScale(side.axis === 'z' ? bay * opening : .012, step * opening, side.axis === 'z' ? .012 : bay * opening)
            matrix.setPosition(side.axis === 'z' ? along : side.sign * (side.reach / 2 + .007), (floor + .5) * step,
              side.axis === 'z' ? side.sign * (side.reach / 2 + .007) : along)
            windows.setMatrixAt(floor * bays + index, matrix)
          }
          windows.instanceMatrix.needsUpdate = true; building.add(windows)
        }
        if (model.facade === 'modular' || model.facade === 'hybrid' || model.facade === 'frame') {
          const ribs = new THREE.InstancedMesh(boxGeometry, model.facade === 'modular' ? jointMaterial : floorMaterial, bays + 1)
          for (let index = 0; index <= bays; index++) {
            const along = index * bay - side.span / 2
            const thickness = model.facade === 'hybrid' ? .045 : model.facade === 'modular' ? .018 : .032
            matrix.makeScale(side.axis === 'z' ? thickness : .027, volume.height, side.axis === 'z' ? .027 : thickness)
            matrix.setPosition(side.axis === 'z' ? along : side.sign * (side.reach / 2 + .015), volume.height / 2,
              side.axis === 'z' ? side.sign * (side.reach / 2 + .015) : along)
            ribs.setMatrixAt(index, matrix)
          }
          ribs.instanceMatrix.needsUpdate = true; ribs.castShadow = true; building.add(ribs)
        }
      }
      const roof = new THREE.Mesh(boxGeometry, roofMaterial)
      roof.scale.set(volume.width + .045, .025, volume.depth + .045)
      roof.position.y = volume.height + .012; roof.castShadow = true; building.add(roof)
      // 屋面凹槽、女儿墙和入口只是建筑表达细节，不是施工图。
      const roofInset = new THREE.Mesh(boxGeometry, rooftopMaterial)
      roofInset.scale.set(volume.width * .80, .009, volume.depth * .76)
      roofInset.position.y = volume.height + .029; building.add(roofInset)
      const roofCore = new THREE.Mesh(boxGeometry, bodyMaterial)
      roofCore.scale.set(volume.width * .27, .11, volume.depth * .26)
      roofCore.position.set(0, volume.height + .085, -.06); roofCore.castShadow = true; building.add(roofCore)
      const roofCap = new THREE.Mesh(boxGeometry, roofMaterial)
      roofCap.scale.set(roofCore.scale.x + .025, .016, roofCore.scale.z + .025)
      roofCap.position.copy(roofCore.position); roofCap.position.y += .062; building.add(roofCap)
      for (const [sx, sz, x, z] of [
        [volume.width, .025, 0, volume.depth / 2], [volume.width, .025, 0, -volume.depth / 2],
        [.025, volume.depth, volume.width / 2, 0], [.025, volume.depth, -volume.width / 2, 0],
      ]) {
        const parapet = new THREE.Mesh(boxGeometry, roofMaterial)
        parapet.scale.set(sx, .07, sz); parapet.position.set(x, volume.height + .05, z); building.add(parapet)
      }
      const plinth = new THREE.Mesh(boxGeometry, floorMaterial)
      plinth.scale.set(volume.width + .045, .065, volume.depth + .045); plinth.position.y = .032; building.add(plinth)
      const entry = new THREE.Mesh(boxGeometry, insetMaterial)
      entry.scale.set(volume.width * .18, Math.min(step * .8, .15), .016)
      entry.position.set(0, entry.scale.y / 2 + .065, volume.depth / 2 + .01); building.add(entry)
      const floors = new THREE.InstancedMesh(boxGeometry, model.facade === 'modular' ? jointMaterial : floorMaterial, volume.floors)
      for (let floor = 0; floor < volume.floors; floor++) {
        matrix.makeScale(volume.width + .025, model.facade === 'wall' ? .009 : .016, volume.depth + .025)
        matrix.setPosition(0, floor / volume.floors * volume.height, 0)
        floors.setMatrixAt(floor, matrix)
      }
      floors.instanceMatrix.needsUpdate = true; floors.castShadow = true; building.add(floors)
      if (model.cantilever) for (const fraction of [.32, .68]) {
        const ledge = new THREE.Mesh(boxGeometry, roofMaterial)
        ledge.scale.set(volume.width + .16, .035, volume.depth + .20)
        ledge.position.set(0, Math.round(volume.floors * fraction) * step, .055)
        ledge.castShadow = true; building.add(ledge)
      }
      volumes.add(building)
    }
    host.dataset.facade = model.facade
    const halfWidth = Math.max(.8, ...model.volumes.map(v => Math.abs(v.x) + v.width / 2))
    const halfDepth = Math.max(.7, ...model.volumes.map(v => Math.abs(v.z) + v.depth / 2))
    plate.scale.set((halfWidth * 2 + 1.1) / 6.45, 1, (halfDepth * 2 + 1.1) / 5.3)
    rim.scale.set(plate.scale.x, 1, plate.scale.z)
    focus.y = Math.max(.7, ...model.volumes.map(v => v.height * .42))
    bounds.setFromObject(world)
    renderer.shadowMap.needsUpdate = true
    requestRender()
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
    targetPitch = THREE.MathUtils.clamp(pointer.pitch + (event.clientY - pointer.y) * .0015, -.12, .16)
    requestRender()
  }
  const up = (event: PointerEvent) => {
    if (event.pointerId !== pointer?.id) return
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
    pointer = undefined; canvas.classList.remove('is-dragging')
    lastTick = 0; lastDraw = 0; requestRender()
  }
  const reset = () => { pauseAuto(); targetYaw = yaw + Math.atan2(Math.sin(-yaw), Math.cos(-yaw)); targetPitch = 0; requestRender() }
  const key = (event: KeyboardEvent) => {
    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key)) return
    event.preventDefault()
    pauseAuto()
    if (event.key === 'Home') reset()
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') targetYaw += event.key === 'ArrowLeft' ? -.12 : .12
    else targetPitch = THREE.MathUtils.clamp(targetPitch + (event.key === 'ArrowUp' ? -.04 : .04), -.10, .14)
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

export default function BuildingScene({ model, onUnavailable, onReady }: { model: BuildingModel; onUnavailable: () => void; onReady: () => void }) {
  const host = useRef<HTMLDivElement>(null)
  const controller = useRef<Controller>()
  const latest = useRef(model)
  latest.current = model
  useEffect(() => {
    if (!host.current) return
    try { controller.current = createScene(host.current, onUnavailable, onReady); controller.current.update(latest.current) }
    catch { controller.current?.dispose(); controller.current = undefined; onUnavailable() }
    return () => { controller.current?.dispose(); controller.current = undefined }
  }, [onUnavailable, onReady])
  useEffect(() => { controller.current?.update(model) }, [model])
  return <>
    <div className="building-canvas" ref={host} data-renderer="webgl" />
    <button className="stage-reset glass-control" type="button" onClick={() => controller.current?.reset()}>复位视角</button>
  </>
}
