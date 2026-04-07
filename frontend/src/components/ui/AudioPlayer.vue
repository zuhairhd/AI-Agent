<template>
  <div
    v-if="src"
    class="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(10,24,45,.96),rgba(12,29,52,.92))] p-4 shadow-[0_10px_30px_rgba(0,0,0,.18)]"
  >
    <div class="flex items-center gap-4">
      <button
        @click="toggle"
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-[#111827] shadow-lg transition-all duration-200 hover:-translate-y-0.5"
        style="background: linear-gradient(135deg, var(--fss-bronze), #d7a476);"
      >
        {{ playing ? '⏸' : '▶' }}
      </button>

      <div class="min-w-0 flex-1">
        <div class="mb-2 flex items-center justify-between gap-3">
          <div class="text-sm font-medium text-white">Call Recording</div>
          <div class="text-xs text-slate-400">
            {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
          </div>
        </div>

        <input
          type="range"
          class="fss-range w-full"
          :max="duration || 0"
          :value="currentTime"
          @input="seek"
        />

        <div class="mt-2 flex items-center justify-between text-xs text-slate-500">
          <span>{{ playing ? 'Playing...' : 'Paused' }}</span>
          <span v-if="duration">{{ Math.round((currentTime / duration) * 100) || 0 }}%</span>
          <span v-else>0%</span>
        </div>
      </div>

      <audio
        ref="audio"
        :src="src"
        @timeupdate="onTime"
        @loadedmetadata="onMeta"
        @ended="onEnded"
      />
    </div>
  </div>

  <div
    v-else
    class="rounded-2xl border border-dashed border-white/10 bg-white/5 px-4 py-5 text-sm italic text-slate-400"
  >
    No recording available
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  src: String,
})

const audio = ref(null)
const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)

function toggle() {
  if (!audio.value) return

  if (playing.value) {
    audio.value.pause()
    playing.value = false
  } else {
    audio.value.play()
    playing.value = true
  }
}

function onTime() {
  currentTime.value = audio.value?.currentTime || 0
}

function onMeta() {
  duration.value = audio.value?.duration || 0
}

function seek(e) {
  if (!audio.value) return
  audio.value.currentTime = Number(e.target.value)
  currentTime.value = Number(e.target.value)
}

function onEnded() {
  playing.value = false
  currentTime.value = duration.value
}

function formatTime(value) {
  if (!value || Number.isNaN(value)) return '0:00'
  const minutes = Math.floor(value / 60)
  const seconds = Math.floor(value % 60)
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}
</script>

<style scoped>
.fss-range {
  -webkit-appearance: none;
  appearance: none;
  height: 8px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.08);
  outline: none;
}

.fss-range::-webkit-slider-runnable-track {
  height: 8px;
  border-radius: 9999px;
  background: linear-gradient(90deg, rgba(196, 146, 102, 0.28), rgba(42, 212, 255, 0.18));
}

.fss-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  margin-top: -4px;
  height: 16px;
  width: 16px;
  border: none;
  border-radius: 9999px;
  background: var(--fss-bronze);
  box-shadow: 0 0 0 3px rgba(196, 146, 102, 0.18);
  cursor: pointer;
}

.fss-range::-moz-range-track {
  height: 8px;
  border-radius: 9999px;
  background: linear-gradient(90deg, rgba(196, 146, 102, 0.28), rgba(42, 212, 255, 0.18));
}

.fss-range::-moz-range-thumb {
  height: 16px;
  width: 16px;
  border: none;
  border-radius: 9999px;
  background: var(--fss-bronze);
  box-shadow: 0 0 0 3px rgba(196, 146, 102, 0.18);
  cursor: pointer;
}
</style>