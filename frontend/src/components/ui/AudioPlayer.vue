<template>
  <div v-if="src" class="bg-gray-50 rounded-lg p-3 flex items-center gap-3 border border-gray-200">
    <button
      @click="toggle"
      class="w-9 h-9 rounded-full flex items-center justify-center text-white transition-colors"
      style="background: var(--fss-bronze)"
    >{{ playing ? '⏸' : '▶' }}</button>
    <div class="flex-1">
      <input type="range" class="w-full accent-fss-bronze" :max="duration" :value="currentTime"
             @input="seek" />
    </div>
    <span class="text-xs text-gray-500 w-16 text-right">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
    <audio ref="audio" :src="src" @timeupdate="onTime" @loadedmetadata="onMeta" @ended="playing=false" />
  </div>
  <div v-else class="text-sm text-gray-400 italic">No recording available</div>
</template>

<script setup>
import { ref } from 'vue'
defineProps({ src: String })
const audio = ref(null)
const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)

function toggle() {
  if (playing.value) { audio.value.pause(); playing.value = false }
  else               { audio.value.play();  playing.value = true  }
}
function onTime()  { currentTime.value = audio.value.currentTime }
function onMeta()  { duration.value = audio.value.duration || 0 }
function seek(e)   { audio.value.currentTime = e.target.value }
function formatTime(s) {
  if (!s || isNaN(s)) return '0:00'
  return `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`
}
</script>
