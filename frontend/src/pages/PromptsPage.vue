<template>
  <div>
    <h1 class="text-xl font-bold text-gray-900 mb-6">Call Prompts</h1>
    <p class="text-sm text-gray-500 mb-6">
      Edit the text and audio for each voice prompt used during calls.
      Changes take effect immediately on the next call.
    </p>

    <LoadingSpinner v-if="loading" />

    <div v-else class="space-y-4">
      <div v-for="prompt in prompts" :key="prompt.stem"
           class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div class="flex items-start justify-between gap-4 mb-3">
          <div>
            <h3 class="font-semibold text-gray-900 text-sm">{{ prompt.stem }}</h3>
            <span class="text-xs text-gray-400">{{ prompt.language }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span :class="prompt.audio_exists ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                  class="text-xs px-2 py-0.5 rounded-full">
              {{ prompt.audio_exists ? 'Audio ready' : 'No audio' }}
            </span>
            <span class="text-xs text-gray-400">v{{ prompt.version }}</span>
          </div>
        </div>

        <textarea v-model="edits[prompt.stem]" rows="3"
                  class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 resize-none mb-3"
                  :placeholder="prompt.text"></textarea>

        <!-- Audio player -->
        <div v-if="prompt.audio_exists && prompt.audio_path" class="mb-3">
          <audio controls class="w-full h-8">
            <source :src="`/static/portal/audio/${prompt.stem}.wav`" type="audio/wav" />
          </audio>
        </div>

        <div class="flex flex-wrap gap-2">
          <button @click="saveText(prompt)"
                  class="px-3 py-1.5 text-sm text-white rounded-lg hover:opacity-90 transition"
                  style="background: var(--fss-bronze)">
            Save Text
          </button>
          <button @click="regen(prompt)" :disabled="regenLoading[prompt.stem]"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 text-gray-700 hover:border-blue-300 transition disabled:opacity-50">
            {{ regenLoading[prompt.stem] ? 'Generating…' : 'Regenerate Audio' }}
          </button>
          <label class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 text-gray-700 cursor-pointer hover:border-gray-400 transition">
            Upload Custom Audio
            <input type="file" accept=".wav,.mp3,.ogg" class="hidden"
                   @change="(e) => uploadAudio(prompt, e)" />
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { getPrompts, updatePrompt, regeneratePrompt, uploadPromptAudio } from '@/api/prompts'
import { useUiStore } from '@/stores/ui'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const uiStore     = useUiStore()
const prompts     = ref([])
const loading     = ref(true)
const edits       = reactive({})
const regenLoading = reactive({})

async function load() {
  loading.value = true
  try {
    prompts.value = (await getPrompts()).data
    prompts.value.forEach(p => { edits[p.stem] = p.text })
  } finally { loading.value = false }
}

async function saveText(prompt) {
  try {
    const text = edits[prompt.stem]?.trim()
    if (!text) return
    const res = (await updatePrompt(prompt.stem, { text })).data
    Object.assign(prompt, res)
    uiStore.addToast(`Saved: ${prompt.stem}`, 'success')
  } catch { uiStore.addToast('Save failed.', 'error') }
}

async function regen(prompt) {
  regenLoading[prompt.stem] = true
  try {
    const res = (await regeneratePrompt(prompt.stem)).data
    Object.assign(prompt, res)
    uiStore.addToast(`Audio regenerated: ${prompt.stem}`, 'success')
  } catch { uiStore.addToast('Regeneration failed.', 'error') }
  finally { regenLoading[prompt.stem] = false }
}

async function uploadAudio(prompt, e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('audio', file)
  try {
    const res = (await uploadPromptAudio(prompt.stem, formData)).data
    Object.assign(prompt, res)
    uiStore.addToast(`Custom audio uploaded: ${prompt.stem}`, 'success')
  } catch { uiStore.addToast('Upload failed.', 'error') }
  finally { e.target.value = '' }
}

onMounted(load)
</script>
