import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import type { BuildingModel } from './building-model'
import { tokens } from '../theme'

interface Controller { update: (model: BuildingModel) => void; reset: () => void; dispose: () => void }

/** 仅在更新、拖动或短过渡时绘制；没有后台自动旋转。 */
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
  renderer.toneMappingExposure = 1.18
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
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
  const camera = new THREE.OrthographicCamera(-5, 5, 4.5, -4.5, .1, 70)
  camera.position.set(8, 7.5, 10)
  camera.lookAt(0, 1.25, 0)
  camera.zoom = 1.22
  const world = new THREE.Group()
  scene.add(world)
  const ambient = new THREE.HemisphereLight(tokens.surface, tokens.scene.edge, 2.3)
  scene.add(ambient)
  const main = new THREE.DirectionalLight(tokens.surface, 3.6)
  main.position.set(-5, 9, 7)
  main.castShadow = true
  cleanups.push(() => main.shadow.dispose())
  main.shadow.mapSize.set(1024, 1024)
  main.shadow.camera.left = -6; main.shadow.camera.right = 6
  main.shadow.camera.top = 6; main.shadow.camera.bottom = -6
  main.shadow.bias = -.001
  scene.add(main)
  const mint = new THREE.PointLight(tokens.glowMint, 5, 20, 1.4)
  mint.position.set(-4, 4, 2); scene.add(mint)
  const lilac = new THREE.PointLight(tokens.glowLilac, 7, 20, 1.4)
  lilac.position.set(5, 5, -3); scene.add(lilac)
  const boxGeometry = keep(new THREE.BoxGeometry(1, 1, 1))
  const bodyMaterial = keep(new THREE.MeshPhysicalMaterial({ color: tokens.scene.building, roughness: .22, metalness: .08, clearcoat: 1, clearcoatRoughness: .12 }))
  const facadeMaterial = keep(new THREE.MeshPhysicalMaterial({ color: tokens.scene.facade, roughness: .16, metalness: .1, transparent: true, opacity: .68, clearcoat: 1 }))
  const roofMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.roof, roughness: .25, metalness: .08 }))
  const floorMaterial = keep(new THREE.MeshStandardMaterial({ color: tokens.scene.roof, roughness: .38, metalness: .12 }))
  const plateGeometry = keep(new RoundedBoxGeometry(6.45, .20, 5.3, 3, .09))
  const plateMaterial = keep(new THREE.MeshPhysicalMaterial({ color: tokens.scene.plate, roughness: .16, metalness: .12, transparent: true, opacity: .76, clearcoat: 1 }))
  const plate = new THREE.Mesh(plateGeometry, plateMaterial)
  plate.position.y = -.14; plate.receiveShadow = true; plate.castShadow = true; world.add(plate)
  const rimGeometry = keep(new RoundedBoxGeometry(6.54, .045, 5.38, 3, .025))
  const rimMaterial = keep(new THREE.MeshPhysicalMaterial({ color: tokens.scene.roof, transparent: true, opacity: .72, roughness: .12, metalness: .2 }))
  const rim = new THREE.Mesh(rimGeometry, rimMaterial)
  rim.position.y = -.06; world.add(rim)
  const shadowGeometry = keep(new THREE.PlaneGeometry(14, 14))
  const shadowMaterial = keep(new THREE.ShadowMaterial({ opacity: .17 }))
  const shadow = new THREE.Mesh(shadowGeometry, shadowMaterial)
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = -.68; shadow.receiveShadow = true; scene.add(shadow)

  let volumes = new THREE.Group()
  world.add(volumes)
  let failed = false, visible = true, ready = false
  let yaw = -.12, targetYaw = yaw, pitch = 0, targetPitch = 0
  let entrance = 1
  const reduce = matchMedia('(prefers-reduced-motion: reduce)')
  const matrix = new THREE.Matrix4()
  const fail = () => { if (!failed && !disposed) { failed = true; cancelAnimationFrame(frame); frame = 0; onUnavailable() } }
  const render = () => {
    frame = 0
    if (disposed || failed || !visible || document.hidden) return
    const ease = reduce.matches ? 1 : .18
    yaw += (targetYaw - yaw) * ease
    pitch += (targetPitch - pitch) * ease
    entrance += (1 - entrance) * (reduce.matches ? 1 : .14)
    world.rotation.y = yaw; world.rotation.x = pitch
    volumes.scale.y = entrance
    try { renderer.render(scene, camera); if (!ready) { ready = true; onReady() } } catch { fail(); return }
    if (Math.abs(targetYaw - yaw) > .001 || Math.abs(targetPitch - pitch) > .001 || entrance < .999) requestRender()
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
      const body = new THREE.Mesh(boxGeometry, bodyMaterial)
      body.scale.set(volume.width, volume.height, volume.depth)
      body.position.y = volume.height / 2; body.castShadow = true; body.receiveShadow = true; building.add(body)
      const facade = new THREE.Mesh(boxGeometry, facadeMaterial)
      facade.scale.set(volume.width * .93, volume.height * .96, volume.depth + .013)
      facade.position.y = volume.height / 2; building.add(facade)
      const roof = new THREE.Mesh(boxGeometry, roofMaterial)
      roof.scale.set(volume.width + .055, .055, volume.depth + .055)
      roof.position.y = volume.height + .025; roof.castShadow = true; building.add(roof)
      const floors = new THREE.InstancedMesh(boxGeometry, floorMaterial, volume.floors)
      for (let floor = 0; floor < volume.floors; floor++) {
        matrix.makeScale(volume.width + .025, .018, volume.depth + .025)
        matrix.setPosition(0, (floor + .3) / volume.floors * volume.height, 0)
        floors.setMatrixAt(floor, matrix)
      }
      floors.instanceMatrix.needsUpdate = true; floors.castShadow = true; building.add(floors)
      // 立面竖向分格只表达材质，非窗墙比或户型设计。
      const mullions = new THREE.InstancedMesh(boxGeometry, floorMaterial, 6)
      for (let index = 0; index < 6; index++) {
        matrix.makeScale(.022, volume.height, .025)
        matrix.setPosition((index % 3 - 1) * volume.width * .25, volume.height / 2, (index < 3 ? 1 : -1) * (volume.depth / 2 + .014))
        mullions.setMatrixAt(index, matrix)
      }
      mullions.instanceMatrix.needsUpdate = true; building.add(mullions)
      volumes.add(building)
    }
    entrance = reduce.matches ? 1 : .76
    requestRender()
  }
  let pointer: { id: number; x: number; y: number; yaw: number; pitch: number } | undefined
  const down = (event: PointerEvent) => {
    if (event.button !== 0) return
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, yaw: targetYaw, pitch: targetPitch }
    canvas.setPointerCapture(event.pointerId)
    canvas.classList.add('is-dragging')
  }
  const move = (event: PointerEvent) => {
    if (event.pointerId !== pointer?.id) return
    targetYaw = THREE.MathUtils.clamp(pointer.yaw + (event.clientX - pointer.x) * .0045, -.78, .65)
    targetPitch = THREE.MathUtils.clamp(pointer.pitch + (event.clientY - pointer.y) * .0015, -.10, .14)
    requestRender()
  }
  const up = (event: PointerEvent) => {
    if (event.pointerId !== pointer?.id) return
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
    pointer = undefined; canvas.classList.remove('is-dragging')
  }
  const reset = () => { targetYaw = -.12; targetPitch = 0; requestRender() }
  const key = (event: KeyboardEvent) => {
    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key)) return
    event.preventDefault()
    if (event.key === 'Home') reset()
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') targetYaw = THREE.MathUtils.clamp(targetYaw + (event.key === 'ArrowLeft' ? -.12 : .12), -.78, .65)
    else targetPitch = THREE.MathUtils.clamp(targetPitch + (event.key === 'ArrowUp' ? -.04 : .04), -.10, .14)
    requestRender()
  }
  const contextLost = (event: Event) => { event.preventDefault(); fail() }
  const visibility = () => {
    if (document.hidden) { cancelAnimationFrame(frame); frame = 0 } else requestRender()
  }
  const motionChange = () => requestRender()
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
    if (!visible) { cancelAnimationFrame(frame); frame = 0 } else requestRender()
  }, { rootMargin: '30px' })
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
