<script setup>
import { ref } from 'vue'
import { currentPeriod, postJSON } from '../api'
import TierLadder from '../components/TierLadder.vue'
import SegmentTable from '../components/SegmentTable.vue'
import DemandCapCard from '../components/DemandCapCard.vue'

const kwh = ref(220)
const peak = ref(false)
const accountId = ref('')
const period = ref(currentPeriod())
const result = ref(null)
const readOnly = ref(false)
const error = ref(null)

const FIELD_LABEL = { demand_kw: '账期需量', cap_kw: '封顶阈值', convert_coef: '折算系数', account_id: '户号' }

const showError = (e) => {
  const label = e.field ? FIELD_LABEL[e.field] || e.field : ''
  error.value = e.message ? `[${e.code || '错误'}${label ? ' · ' + label : ''}] ${e.message}` : String(e)
}

const commonBody = () => ({
  kwh: kwh.value,
  peak: peak.value,
  period: period.value || null,
  account_id: accountId.value === '' ? null : Number(accountId.value),
})

const probe = async () => {
  error.value = null
  try {
    result.value = await postJSON('/api/demand-cap/probe', commonBody())
    readOnly.value = true
  } catch (e) { showError(e) }
}

const run = async () => {
  error.value = null
  try {
    result.value = await postJSON('/api/bill', { ...commonBody(), persist: true })
    readOnly.value = false
  } catch (e) { showError(e) }
}
</script>
<template>
  <div class="page work">
    <h1>测算工作台</h1>
    <div class="panel form-row">
      <label>电量(kWh) <input type="number" v-model.number="kwh" min="0" step="1" /></label>
      <label><input type="checkbox" v-model="peak" /> 尖峰系数</label>
      <label>户号(可选) <input type="number" v-model="accountId" min="1" step="1" placeholder="自动取封顶参数" /></label>
      <label>账期 <input type="month" v-model="period" /></label>
      <button class="ghost" @click="probe">只读探针试算</button>
      <button @click="run">计算并入库</button>
    </div>
    <p v-if="error" class="err">{{ error }}</p>

    <div v-if="result" class="panel">
      <p class="muted">
        {{ readOnly ? '探针试算（不写运行、不改户参数）' : `已入库 · 记录#${result.run_id}` }}
      </p>
      <DemandCapCard :cap="result.demand_cap" />
      <div class="qty-grid">
        <div><div class="muted">基础电量</div><strong>{{ result.base_kwh }} kWh</strong></div>
        <div><div class="muted">附加电量</div><strong>{{ result.extra_kwh }} kWh</strong></div>
        <div><div class="muted">合并净电量</div><strong>{{ result.net_kwh }} kWh</strong></div>
        <div><div class="muted">合计</div><strong class="hero-num" style="font-size:1.6rem">¥{{ result.total }}</strong></div>
      </div>
      <p class="muted" v-if="result.demand_cap?.capped">
        附加电量并入净电量后再走阶梯与尖峰；来源：{{ result.demand_cap.extra_source }}
      </p>
      <TierLadder :segments="result.segments" />
      <SegmentTable :rows="result.segments" />
    </div>
  </div>
</template>
<style scoped>
.form-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: end; }
input[type=number] { width: 7rem; margin-left: 0.35rem; }
.ghost { background: transparent; border: 1px solid var(--accent); color: var(--accent); }
.err { color: #ff7a7a; }
.qty-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin: 0.5rem 0 1rem; }
.qty-grid > div { background: #0d1612; padding: 0.6rem 0.75rem; border-radius: 8px; }
</style>
