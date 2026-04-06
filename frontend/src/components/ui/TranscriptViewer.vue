<template>
  <div class="space-y-4">
    <div v-if="!turns || turns.length === 0" class="text-sm text-gray-400 italic">No conversation turns available.</div>
    <div v-for="turn in turns" :key="turn.id" class="space-y-2">
      <!-- Caller speech -->
      <div v-if="turn.transcript_text" class="flex gap-3">
        <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm flex-shrink-0">👤</div>
        <div class="max-w-lg">
          <div class="text-xs text-gray-400 mb-1">Caller · Turn {{ turn.turn_number }}</div>
          <div class="bg-blue-50 border border-blue-100 rounded-xl rounded-tl-none px-4 py-3 text-sm text-gray-800">
            {{ turn.transcript_text }}
          </div>
        </div>
      </div>
      <!-- AI response -->
      <div v-if="turn.ai_response_text" class="flex gap-3 justify-end">
        <div class="max-w-lg">
          <div class="text-xs text-gray-400 mb-1 text-right">AI Assistant</div>
          <div class="rounded-xl rounded-tr-none px-4 py-3 text-sm text-white"
               style="background: var(--fss-bronze)">
            {{ turn.ai_response_text }}
          </div>
          <div v-if="turn.ai_confidence_score !== null && turn.ai_confidence_score !== undefined"
               class="text-xs text-gray-400 mt-1 text-right">
            Confidence: {{ Math.round(turn.ai_confidence_score * 100) }}%
          </div>
        </div>
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0"
             style="background: var(--fss-bronze); color: white">🤖</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ turns: Array })
</script>
