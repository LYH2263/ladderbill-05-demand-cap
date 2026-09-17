<script setup>
import { computed } from 'vue'
const props = defineProps({
  cap: { type: Object, default: null },
})
const triggered = computed(() => !!props.cap?.capped)
</script>
<template>
  <div class="panel cap-card" :class="{ on: triggered }">
    <div class="cap-head">
      <h3>需量封顶</h3>
      <span class="badge" :class="triggered ? 'yes' : 'no'">
        {{ triggered ? '已触发封顶' : '未触发封顶' }}
      </span>
    </div>
    <table v-if="cap && cap.demand_kw != null">
      <tbody>
        <tr><td class="muted">账期需量</td><td>{{ cap.demand_kw }} kW</td></tr>
        <tr><td class="muted">封顶阈值</td><td>{{ cap.cap_kw }} kW</td></tr>
        <tr><td class="muted">折算系数</td><td>{{ cap.convert_coef }}</td></tr>
        <tr><td class="muted">超额需量</td><td>{{ cap.excess_kw }} kW</td></tr>
        <tr><td class="muted">附加电量</td><td><strong>{{ cap.extra_kwh }} kWh</strong></td></tr>
      </tbody>
    </table>
    <p v-else class="muted">该账期未配置需量封顶参数，附加电量按 0 计。</p>
    <p v-if="cap?.extra_source" class="source">来源：{{ cap.extra_source }}</p>
    <p v-else-if="cap && cap.demand_kw != null" class="muted">需量未超过阈值，附加电量为 0。</p>
  </div>
</template>
<style scoped>
.cap-card { border: 1px solid color-mix(in srgb, var(--muted) 35%, transparent); }
.cap-card.on { border-color: #e6a817; }
.cap-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }
.cap-head h3 { margin: 0; }
.badge { padding: 0.2rem 0.55rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
.badge.yes { background: rgba(230, 168, 23, 0.18); color: #e6a817; }
.badge.no { background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }
.source { color: #e6a817; margin: 0.5rem 0 0; }
</style>
