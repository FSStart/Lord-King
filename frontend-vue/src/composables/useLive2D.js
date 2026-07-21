import { ref, onMounted, onUnmounted } from "vue"

export function useLive2D(canvasRef) {
  const isLoaded = ref(false)
  const currentEmotion = ref("neutral")
  let pixiApp = null
  let model = null

  async function init() {
    if (!canvasRef.value) return

    // Wait for Live2D libraries to load
    await waitForLibs()

    try {
      const PIXI = window.PIXI
      const app = new PIXI.Application({
        view: canvasRef.value,
        width: 320,
        height: 480,
        transparent: true,
        antialias: true,
        autoStart: true,
      })
      pixiApp = app

      // Load model
      const modelData = await PIXI.live2d.SdkSetting.load("/models/hiyori/model.json")
      model = PIXI.live2d.Live2DModel.fromSync(modelData)
      app.stage.addChild(model)

      const scale = Math.min(320 / model.width, 480 / model.height) * 2.0
      model.scale.set(scale)
      model.anchor.set(0.5, 0.5)
      model.position.set(160, 240)

      isLoaded.value = true
    } catch (e) {
      console.error("Live2D init failed:", e)
    }
  }

  async function waitForLibs() {
    return new Promise((resolve) => {
      let attempts = 0
      const check = () => {
        if (window.PIXI?.live2d && window.Live2DCubismCore) return resolve()
        if (++attempts > 100) return resolve()
        setTimeout(check, 100)
      }
      check()
    })
  }

  function setEmotion(emotion) {
    if (!model) return
    const emotionMap = {
      happy: 0, shy: 1, sad: 2, angry: 3, surprised: 4, love: 5, neutral: 0,
    }
    const idx = emotionMap[emotion] ?? 0
    try { model.expression(idx) } catch (e) {}
    currentEmotion.value = emotion
  }

  function triggerMotion(group) {
    if (!model) return
    try { model.motion(group || "idle") } catch (e) {}
  }

  onMounted(init)
  onUnmounted(() => {
    if (pixiApp) pixiApp.destroy(true)
  })

  return { isLoaded, currentEmotion, setEmotion, triggerMotion }
}
