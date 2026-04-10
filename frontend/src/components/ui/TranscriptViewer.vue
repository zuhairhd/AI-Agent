<template>
  <div class="space-y-4">
    <div v-if="!turns || turns.length === 0" class="text-sm text-gray-400 italic">No conversation turns available.</div>
    <div v-for="turn in turns" :key="turn.id" class="space-y-2">

      <!-- Caller speech -->
      <div class="flex gap-3">
        <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm flex-shrink-0">👤</div>
        <div class="flex-1 min-w-0">
          <div class="text-xs text-gray-400 mb-1">Caller · Turn {{ turn.turn_number }}</div>
          <div v-if="turn.transcript_text"
               class="bg-blue-50 border border-blue-100 rounded-xl rounded-tl-none px-4 py-3 text-sm text-gray-800">
            {{ turn.transcript_text }}
          </div>
          <div v-else class="text-xs text-gray-400 italic">Transcription not available</div>

          <!-- Caller recording audio player / fallback -->
          <template v-if="sessionId">
            <audio v-if="turn.audio_input_path && !inputErrors.has(turn.id)"
                   controls preload="none"
                   class="w-full mt-1" style="height:32px"
                   @error="inputErrors.add(turn.id)">
              <source :src="`/api/portal/calls/${sessionId}/recording/${turn.id}/?type=input`" type="audio/wav" />
            </audio>
            <p v-else class="text-xs text-gray-400 italic mt-1">
              {{ inputErrors.has(turn.id) ? 'Audio not available' : 'No recording' }}
            </p>
          </template>
        </div>
      </div>

      <!-- AI response -->
      <div class="flex gap-3 justify-end">
        <div class="flex-1 min-w-0">
          <div class="text-xs text-gray-400 mb-1 text-right">AI Assistant</div>
          <div v-if="turn.ai_response_text"
               class="rounded-xl rounded-tr-none px-4 py-3 text-sm text-white"
               style="background: var(--fss-bronze)">
            {{ turn.ai_response_text }}
          </div>
          <div v-else class="text-xs text-gray-400 italic text-right">Response not available</div>
          <div v-if="turn.ai_confidence_score !== null && turn.ai_confidence_score !== undefined"
               class="text-xs text-gray-400 mt-1 text-right">
            Confidence: {{ Math.round(turn.ai_confidence_score * 100) }}%
          </div>

          <!-- AI response audio player / fallback -->
          <template v-if="sessionId">
            <audio v-if="turn.audio_response_exists && !responseErrors.has(turn.id)"
                   controls preload="none"
                   class="w-full mt-1" style="height:32px"
                   @error="responseErrors.add(turn.id)">
              <source :src="`/api/portal/calls/${sessionId}/recording/${turn.id}/?type=response`" type="audio/wav" />
            </audio>
            <p v-else class="text-xs text-gray-400 italic mt-1 text-right">
              {{ responseErrors.has(turn.id) ? 'Audio not available' : 'Response audio not generated' }}
            </p>
          </template>
        </div>
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0"
             style="background: var(--fss-bronze); color: white">🤖</div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

defineProps({
  turns:     Array,
  sessionId: String,
})

// Track audio load errors per turn so we can swap to fallback text
const inputErrors    = reactive(new Set())
const responseErrors = reactive(new Set())
</script>
