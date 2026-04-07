<template>
  <div class="relative min-h-screen overflow-hidden bg-[#071426] text-white">
    <!-- Background image -->
    <div
      class="absolute inset-0 opacity-20 pointer-events-none"
      :style="{
        backgroundImage: `url(${coverImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      }"
    ></div>

    <!-- Overlays -->
    <div
      class="absolute inset-0 pointer-events-none"
      style="background:
        radial-gradient(circle at 18% 20%, rgba(196,146,102,.16), transparent 28%),
        radial-gradient(circle at 82% 18%, rgba(42,212,255,.10), transparent 26%),
        linear-gradient(180deg, rgba(7,20,38,.88), rgba(7,20,38,.96));"
    ></div>

    <!-- Top nav -->
    <header class="relative z-20 px-6 py-5 lg:px-10">
      <div class="mx-auto flex max-w-7xl items-center justify-between">
        <div class="flex items-center gap-4">
          <div class="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5 shadow-xl backdrop-blur-md">
            <img :src="logo" alt="Future Smart Support" class="h-10 w-10 object-contain" />
          </div>
          <div>
            <div class="text-xl font-bold tracking-tight">Future Smart Support</div>
            <div class="text-sm text-slate-300">Where Artificial Intelligence Powers Creativity</div>
          </div>
        </div>

        <div class="hidden md:flex items-center gap-3">
          <a
            href="/portal/login"
            class="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/10"
          >
            Portal Login
          </a>
          <a
            href="/admin/"
            class="rounded-xl px-4 py-2 text-sm font-semibold text-[#111827] shadow-[0_10px_24px_rgba(196,146,102,0.28)] transition hover:scale-[1.02]"
            style="background: linear-gradient(135deg, #c49266, #d7a476)"
          >
            Admin
          </a>
        </div>
      </div>
    </header>

    <!-- Hero -->
    <main class="relative z-10 px-6 pb-14 pt-8 lg:px-10 lg:pt-16">
      <div class="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
        <!-- Left -->
        <section>
          <div class="inline-flex rounded-full border border-[rgba(196,146,102,.24)] bg-[rgba(196,146,102,.10)] px-4 py-1.5 text-sm font-medium text-[#d7a476]">
            AI Support • Smart Monitoring • Follow-up Intelligence
          </div>

          <h1 class="mt-6 text-5xl font-bold leading-[1.05] tracking-tight text-white lg:text-6xl">
            Smarter support operations for modern teams.
          </h1>

          <p class="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            Future Smart Support helps you manage AI-powered calls, alerts, follow-ups,
            and operational visibility through a professional portal built for fast decisions.
          </p>

          <div class="mt-8 flex flex-wrap gap-4">
            <a
              href="/portal/login"
              class="rounded-2xl px-6 py-3 text-sm font-semibold text-[#111827] shadow-[0_12px_28px_rgba(196,146,102,.28)] transition hover:scale-[1.02]"
              style="background: linear-gradient(135deg, #c49266, #d7a476)"
            >
              Open Portal
            </a>

            <a
              href="/admin/"
              class="rounded-2xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-medium text-slate-200 transition hover:bg-white/10"
            >
              Open Admin
            </a>
          </div>

          <div class="mt-10 grid gap-4 sm:grid-cols-3">
            <div class="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md">
              <div class="text-2xl font-bold text-[#d7a476]">Live</div>
              <div class="mt-1 text-sm text-slate-300">Call Monitoring</div>
            </div>
            <div class="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md">
              <div class="text-2xl font-bold text-[#d7a476]">Smart</div>
              <div class="mt-1 text-sm text-slate-300">Follow-up Alerts</div>
            </div>
            <div class="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md">
              <div class="text-2xl font-bold text-[#d7a476]">Secure</div>
              <div class="mt-1 text-sm text-slate-300">Admin Access</div>
            </div>
          </div>
        </section>

        <!-- Right -->
        <section class="relative">
          <div
            class="absolute inset-0 rounded-[32px] blur-3xl opacity-30"
            style="background: radial-gradient(circle, rgba(196,146,102,.35), transparent 60%)"
          ></div>

          <div class="relative overflow-hidden rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(10,24,45,.94),rgba(12,29,52,.92))] p-6 shadow-[0_25px_60px_rgba(0,0,0,.35)]">
            <img
              :src="coverImage"
              alt="Future Smart Support"
              class="h-[420px] w-full rounded-2xl object-cover object-center"
            />

            <div class="mt-6 grid gap-4 sm:grid-cols-2">
              <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div class="text-sm font-semibold text-white">Portal Access</div>
                <div class="mt-2 text-sm text-slate-300">
                  Monitor calls, alerts, and follow-up activity from one dashboard.
                </div>
              </div>

              <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div class="text-sm font-semibold text-white">Administration</div>
                <div class="mt-2 text-sm text-slate-300">
                  Manage configuration, users, and operational controls securely.
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- Footer -->
      <footer class="mx-auto mt-16 max-w-7xl border-t border-white/10 pt-6 text-sm text-slate-400">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            © {{ year }} Future Smart Support
          </div>

          <div class="flex flex-col gap-1 md:flex-row md:gap-6">
            <span>majid@FutureSmartSupport.com</span>
            <span>GSM: 92771730</span>
            <span>futuresmartsupport.com</span>
          </div>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup>
import logo from '@/assets/branding/FSS_Logo.svg'
import coverImage from '@/assets/branding/cover_image.png'

const year = new Date().getFullYear()
</script>